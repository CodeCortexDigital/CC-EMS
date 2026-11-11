import os
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from django.apps import apps
from django.db.models import Avg, Q, Sum

from predictions.model_store import is_trusted, load_signed, save_signed

try:
    from xgboost import XGBClassifier
    XGBOOST_AVAILABLE = True
except ImportError:
    from sklearn.ensemble import GradientBoostingClassifier as XGBClassifier
    XGBOOST_AVAILABLE = False

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Bump when the inputs of a model change, so a model saved by an older version is never loaded against new inputs.
MODEL_VERSION = "v2"
# The documented rules the models are fitted to (there are no recorded outcomes to learn from; see risk_model_card in the app).
FEE_RULE_OVERDUE_SHARE = 0.4            # a student counts as a fee-default risk when 40% or more of what was billed is overdue and unpaid
DROPOUT_RULE_THRESHOLD = 0.45           # score = 0.5 * (1 - attendance) + 0.3 * (1 - exam average) + 0.1 * behaviour concerns
FEE_FEATURES = ["unpaid_ratio"]
DROPOUT_FEATURES = ["attendance_rate", "exam_avg", "behavior_concerns"]
SYNTHETIC_ROWS = 200
# What the last training used, for the scan record and the model card.
LAST_TRAINING: dict = {}


def get_tenant_model_paths(tenant_id: str) -> tuple:
    """Returns absolute paths for serialized pkl models based on tenant ID."""
    tenant_str = str(tenant_id) if tenant_id else "default"
    fee_path = os.path.join(CURRENT_DIR, f"fee_model_{MODEL_VERSION}_{tenant_str}.pkl")
    dropout_path = os.path.join(CURRENT_DIR, f"dropout_model_{MODEL_VERSION}_{tenant_str}.pkl")
    return fee_path, dropout_path

def get_student_predictive_features(student) -> dict:
    """Extracts features for both Fee Default and Dropout models."""
    AttendanceRecord = apps.get_model('education_attendance', 'AttendanceRecord')
    ExamResult = apps.get_model('education_exams', 'ExamResult')
    Invoice = apps.get_model('education_finance', 'Invoice')
    TeacherFeedback = apps.get_model('education_academics', 'TeacherFeedback')
    
    # 1. Attendance Rate
    # Holidays are not school days. Present, late, early-dismissal and excused days all count as attended: being excused is not a risk sign.
    day_records = AttendanceRecord.objects.filter(student=student).exclude(status='holiday')
    att_total = day_records.count()
    att_present = day_records.filter(status__in=['present', 'late', 'early_dismissal', 'excused']).count()
    att_rate = (att_present / att_total * 100.0) if att_total > 0 else 92.0
    
    # 2. Exam Average Percentage
    exam_avg = ExamResult.objects.filter(student=student).aggregate(Avg('percentage'))['percentage__avg'] or 78.0
    
    # 3. Overdue balance ratio: only what is past its due date counts. An invoice issued last week and not yet due is not a risk sign.
    import datetime
    today = datetime.date.today()
    invoices = Invoice.objects.filter(student=student)
    total_invoiced = float(invoices.aggregate(Sum('amount'))['amount__sum'] or 0.0)
    overdue = invoices.filter(due_date__lt=today)
    overdue_unpaid = float(overdue.aggregate(Sum('amount'))['amount__sum'] or 0.0) - float(overdue.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0.0)
    unpaid_ratio = max(0.0, overdue_unpaid) / total_invoiced if total_invoiced > 0 else 0.0

    # 6. Behavior concerns count
    behavior_concerns = TeacherFeedback.objects.filter(
        student=student, 
        feedback_type__in=['behavior', 'concern']
    ).count()
    
    # Missing data is filled with a typical value so a score can still be produced, and the gap is reported with the score.
    gaps = []
    if att_total == 0:
        gaps.append("no attendance records (92% assumed)")
    if not ExamResult.objects.filter(student=student).exists():
        gaps.append("no exam results (78% assumed)")
    return {
        "attendance_rate": float(att_rate),
        "exam_avg": float(exam_avg),
        "unpaid_ratio": float(unpaid_ratio),
        "behavior_concerns": int(behavior_concerns),
        "data_gaps": gaps,
    }

def train_and_save_fee_dropout_models(tenant_id=None) -> str:
    """Trains Logistic Regression (Fee Default) and XGBoost (Dropout) models on synthetic & real data.

    `tenant_id` scopes training to one school (plus legacy rows with no tenant set); without it
    every school's students would be pooled into one shared "default" model."""
    Student = apps.get_model('education_students', 'Student')
    students = Student.objects.filter(is_active=True)
    if tenant_id:
        students = students.filter(Q(tenant_id=tenant_id) | Q(tenant_id__isnull=True))

    # Fetch real records features
    real_rows = []
    for s in students:
        real_rows.append(get_student_predictive_features(s))
        
    df_real = pd.DataFrame(real_rows)
    
    # Synthetic rows are added so the models can be fitted when a school has few students. They follow the same documented rules.
    np.random.seed(88)
    n_samples = SYNTHETIC_ROWS

    synthetic_data = {
        "attendance_rate": np.random.uniform(60.0, 100.0, n_samples),
        "exam_avg": np.random.uniform(45.0, 100.0, n_samples),
        "unpaid_ratio": np.random.uniform(0.0, 1.0, n_samples),
        "behavior_concerns": np.random.choice([0, 1, 2, 3, 4], n_samples, p=[0.6, 0.2, 0.1, 0.07, 0.03])
    }
    df_synth = pd.DataFrame(synthetic_data)
    df_synth["fee_default"] = (df_synth["unpaid_ratio"] >= FEE_RULE_OVERDUE_SHARE).astype(int)
    df_synth["dropout"] = [
        1 if (1.0 - att / 100.0) * 0.5 + (1.0 - ex / 100.0) * 0.3 + bc * 0.1 > DROPOUT_RULE_THRESHOLD else 0
        for att, ex, bc in zip(df_synth["attendance_rate"], df_synth["exam_avg"], df_synth["behavior_concerns"])
    ]

    # Combine real and synthetic datasets. The labels of real rows come from the same rules: no real outcome is recorded.
    if not df_real.empty:
        df_real = df_real[FEE_FEATURES + DROPOUT_FEATURES].copy()
        df_real["fee_default"] = (df_real["unpaid_ratio"] >= FEE_RULE_OVERDUE_SHARE).astype(int)
        df_real["dropout"] = [
            1 if (1.0 - r["attendance_rate"] / 100.0) * 0.5 + (1.0 - r["exam_avg"] / 100.0) * 0.3 + r["behavior_concerns"] * 0.1 > DROPOUT_RULE_THRESHOLD else 0
            for r in df_real.to_dict("records")
        ]
        df_combined = pd.concat([df_real, df_synth], ignore_index=True)
    else:
        df_combined = df_synth

    # 1. Fit Fee Default Model (Logistic Regression)
    X_fee = df_combined[FEE_FEATURES]
    y_fee = df_combined["fee_default"]
    fee_model = LogisticRegression(random_state=42)
    fee_model.fit(X_fee, y_fee)
    
    # 2. Fit Dropout Model (XGBoost/Light Classifier)
    X_drop = df_combined[DROPOUT_FEATURES]
    y_drop = df_combined["dropout"]
    
    if XGBOOST_AVAILABLE:
        # XGBoost requires numeric evaluation
        dropout_model = XGBClassifier(n_estimators=50, max_depth=3, random_state=42, eval_metric='logloss')
    else:
        dropout_model = XGBClassifier(n_estimators=50, max_depth=3, random_state=42)
        
    dropout_model.fit(X_drop, y_drop)
    
    # Save both models
    fee_path, dropout_path = get_tenant_model_paths(tenant_id)
    save_signed(fee_model, fee_path)
    save_signed(dropout_model, dropout_path)
        
    LAST_TRAINING.clear()
    LAST_TRAINING.update({
        "real_rows": len(real_rows), "synthetic_rows": n_samples, "model_version": MODEL_VERSION,
        "fee_algorithm": "Logistic regression", "dropout_algorithm": "XGBoost" if XGBOOST_AVAILABLE else "Gradient boosting (XGBoost not installed)",
        "fee_features": FEE_FEATURES, "dropout_features": DROPOUT_FEATURES,
    })
    return f"Fee & Dropout models trained successfully (XGBoost: {'True' if XGBOOST_AVAILABLE else 'False Fallback'})."

def predict_fee_dropout_risk(student, tenant_id=None) -> dict:
    """Predicts Fee Default risk and Dropout risk for a given student."""
    fee_path, dropout_path = get_tenant_model_paths(tenant_id)
    
    # Ensure models exist
    # (a file that is missing, unsigned or changed since it was saved is not loaded: a fresh model is trained instead)
    if not is_trusted(fee_path) or not is_trusted(dropout_path):
        train_and_save_fee_dropout_models(tenant_id)

    fee_model = load_signed(fee_path)
    dropout_model = load_signed(dropout_path)
        
    features = get_student_predictive_features(student)
    
    # Predict fee default risk probability
    X_fee = pd.DataFrame([{"unpaid_ratio": features["unpaid_ratio"]}])
    fee_prob = float(fee_model.predict_proba(X_fee)[0][1]) * 100.0
    
    # Predict dropout risk probability
    X_drop = pd.DataFrame([{
        "attendance_rate": features["attendance_rate"],
        "exam_avg": features["exam_avg"],
        "behavior_concerns": features["behavior_concerns"]
    }])
    dropout_prob = float(dropout_model.predict_proba(X_drop)[0][1]) * 100.0
    
    return {
        "fee_default_risk": fee_prob,
        "dropout_risk": dropout_prob,
        "features": features
    }
