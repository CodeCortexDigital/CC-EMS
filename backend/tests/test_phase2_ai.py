import pytest
from django.urls import reverse
from rest_framework import status
from django.apps import apps
from django.utils import timezone
from django.contrib.auth import get_user_model
# The ai-ml packages are optional (see ai-ml/requirements.txt; the app switches these features off without them),
# so this module is skipped where they are not installed, e.g. in CI.
np = pytest.importorskip('numpy')
pytest.importorskip('sklearn')
pytest.importorskip('pandas')

import os
import sys

# Add ai-ml path dynamically
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ai_ml_path = os.path.abspath(os.path.join(BASE_DIR, "..", "ai-ml"))
if os.name == "nt" and len(ai_ml_path) > 1 and ai_ml_path[1] == ":":
    ai_ml_path = ai_ml_path[0].upper() + ai_ml_path[1:]
if ai_ml_path not in sys.path:
    sys.path.append(ai_ml_path)

from attendance.face_recognizer import get_hash_embedding, match_embeddings, extract_embedding_from_image
from predictions.dropout_fee_model import train_and_save_fee_dropout_models, predict_fee_dropout_risk
from academics.timetable_optimizer import optimize_timetable
from academics.quiz_generator import generate_ai_quiz

User = get_user_model()

@pytest.mark.django_db
class TestPhase2FaceRecognition:
    def test_hash_embedding_generation(self):
        emb1 = get_hash_embedding("student_1")
        emb2 = get_hash_embedding("student_1")
        emb3 = get_hash_embedding("student_2")
        
        assert len(emb1) == 128
        assert emb1 == emb2
        assert emb1 != emb3
        
        # Test normalization (should have magnitude close to 1)
        mag = np.linalg.norm(np.array(emb1))
        assert pytest.approx(mag, 0.001) == 1.0

    def test_embedding_matching(self):
        emb1 = get_hash_embedding("student_1")
        emb2 = get_hash_embedding("student_1")
        emb3 = get_hash_embedding("student_2")
        
        score_identical = match_embeddings(emb1, emb2)
        score_diff = match_embeddings(emb1, emb3)
        
        assert pytest.approx(score_identical, 0.01) == 100.0
        assert score_diff < 100.0

@pytest.mark.django_db
class TestPhase2PredictiveModels:
    def test_feature_extraction_and_training(self):
        # Trigger training to verify it executes successfully on synthetic data
        msg = train_and_save_fee_dropout_models()
        assert "trained successfully" in msg

    def test_risk_predictions(self):
        Student = apps.get_model('education_students', 'Student')
        SchoolClass = apps.get_model('education_academics', 'SchoolClass')
        AcademicYear = apps.get_model('education_academics', 'AcademicYear')
        
        # Create mock academic entities
        year = AcademicYear.objects.create(name='2026-2027', start_date='2026-04-01', end_date='2027-03-31', is_active=True)
        cls = SchoolClass.objects.create(code='GRD-TEST', name='Test Class', academic_year=year)
        
        student = Student.objects.create(
            student_id="STU-TEST-999",
            full_name="Intervention Test Student",
            email="test_intervention@code.com",
            current_class=cls,
            is_active=True
        )
        
        risks = predict_fee_dropout_risk(student)
        assert "fee_default_risk" in risks
        assert "dropout_risk" in risks
        assert "features" in risks

    def test_scan_is_scoped_to_one_tenant(self):
        """A risk scan for one school must not score (or train on) another school's students
        (docs table "AI Attendance Insights") — regression test for the shared "default" model bug."""
        from services.analytics.ai_views import _run_risk_scan
        from tests.conftest import SchoolFactory, StudentFactory

        Student = apps.get_model('education_students', 'Student')
        StudentRisk = apps.get_model('analytics', 'StudentRisk')

        school_a = SchoolFactory()
        school_b = SchoolFactory()
        student_a = StudentFactory(tenant=school_a, is_active=True)
        student_b = StudentFactory(tenant=school_b, is_active=True)

        _run_risk_scan(str(school_a.id))

        assert StudentRisk.objects.filter(student=student_a).exists()
        assert not StudentRisk.objects.filter(student=student_b).exists()

@pytest.mark.django_db
class TestPhase2TimetableOptimizer:
    def test_timetable_ga(self):
        AcademicYear = apps.get_model('education_academics', 'AcademicYear')
        SchoolClass = apps.get_model('education_academics', 'SchoolClass')
        Subject = apps.get_model('education_academics', 'Subject')
        ClassSubject = apps.get_model('education_academics', 'ClassSubject')
        Teacher = apps.get_model('education_academics', 'Teacher')
        Classroom = apps.get_model('education_academics', 'Classroom')
        Period = apps.get_model('education_academics', 'Period')
        TeacherSubjectAssignment = apps.get_model('education_academics', 'TeacherSubjectAssignment')
        Section = apps.get_model('education_academics', 'Section')
        
        # Create year
        year = AcademicYear.objects.create(name='2026-2027', start_date='2026-04-01', end_date='2027-03-31', is_active=True)
        
        # Create subject, class, and assignment
        subj = Subject.objects.create(code='SUBJ-001', name='English')
        cls = SchoolClass.objects.create(code='GRD-01', name='Grade 1', academic_year=year)
        sec = Section.objects.create(class_ref=cls, name='A', capacity=15)
        class_subj = ClassSubject.objects.create(class_ref=cls, subject=subj)
        
        teacher = Teacher.objects.create(
            employee_id="TCH-GA-TEST",
            full_name="GA Test Teacher",
            email="gateacher@code.com",
            phone="12345678",
            joining_date="2026-06-24"
        )
        TeacherSubjectAssignment.objects.create(teacher=teacher, class_subject=class_subj, academic_year=year)
        
        Classroom.objects.create(name="Room A", code="ROOM-A", capacity=30, is_active=True)
        Period.objects.create(academic_year=year, period_number=1, start_time="08:00:00", end_time="09:00:00", duration_minutes=60, is_break=False, is_active=True)
        
        res = optimize_timetable(year.id, generations=5, pop_size=10)
        assert res["status"] == "success"
        assert res["slots_scheduled"] > 0

    def test_schedules_periods_per_week_without_double_booking_the_section(self):
        """A subject with periods_per_week=3 gets 3 separate lessons, never in the same slot
        (docs table "AI Timetable Generator")."""
        AcademicYear = apps.get_model('education_academics', 'AcademicYear')
        SchoolClass = apps.get_model('education_academics', 'SchoolClass')
        Subject = apps.get_model('education_academics', 'Subject')
        ClassSubject = apps.get_model('education_academics', 'ClassSubject')
        Teacher = apps.get_model('education_academics', 'Teacher')
        Classroom = apps.get_model('education_academics', 'Classroom')
        Period = apps.get_model('education_academics', 'Period')
        TeacherSubjectAssignment = apps.get_model('education_academics', 'TeacherSubjectAssignment')
        Section = apps.get_model('education_academics', 'Section')
        TimetableEntry = apps.get_model('education_academics', 'TimetableEntry')

        year = AcademicYear.objects.create(name='2026-2027', start_date='2026-04-01', end_date='2027-03-31', is_active=True)
        subj = Subject.objects.create(code='SUBJ-PPW', name='Maths')
        cls = SchoolClass.objects.create(code='GRD-PPW', name='Grade PPW', academic_year=year)
        sec = Section.objects.create(class_ref=cls, name='A', capacity=15)
        cs = ClassSubject.objects.create(class_ref=cls, subject=subj, periods_per_week=3)
        teacher = Teacher.objects.create(employee_id='TCH-PPW', full_name='PPW Teacher',
                                         email='ppw@code.com', phone='12345678', joining_date='2026-06-24')
        TeacherSubjectAssignment.objects.create(teacher=teacher, class_subject=cs, academic_year=year)
        Classroom.objects.create(name='Room PPW', code='ROOM-PPW', capacity=30, is_active=True)
        for i, t in enumerate(['08:00:00', '09:00:00', '10:00:00', '11:00:00', '12:00:00'], start=1):
            Period.objects.create(academic_year=year, period_number=i, start_time=t,
                                  end_time=f'{int(t[:2]) + 1:02d}:00:00', duration_minutes=60, is_break=False, is_active=True)

        res = optimize_timetable(year.id, generations=30, pop_size=30)
        assert res['status'] == 'success'
        entries = list(TimetableEntry.objects.filter(academic_year=year, class_subject=cs))
        assert len(entries) == 3
        slots = {(e.day_of_week, e.period_id) for e in entries}
        assert len(slots) == 3  # no two lessons share a day+period

    def test_scoped_to_one_school(self):
        """Optimising one school's timetable must not use, or overwrite, another school's rooms,
        sections or timetable entries (docs table "AI Timetable Generator")."""
        from services.core.tenants.models import School

        AcademicYear = apps.get_model('education_academics', 'AcademicYear')
        SchoolClass = apps.get_model('education_academics', 'SchoolClass')
        Subject = apps.get_model('education_academics', 'Subject')
        ClassSubject = apps.get_model('education_academics', 'ClassSubject')
        Teacher = apps.get_model('education_academics', 'Teacher')
        Classroom = apps.get_model('education_academics', 'Classroom')
        Period = apps.get_model('education_academics', 'Period')
        TeacherSubjectAssignment = apps.get_model('education_academics', 'TeacherSubjectAssignment')
        Section = apps.get_model('education_academics', 'Section')
        TimetableEntry = apps.get_model('education_academics', 'TimetableEntry')

        school_a = School.objects.create(tenant_code='TTA', name='Tenant A', subdomain='ttopt-tenant-a')
        school_b = School.objects.create(tenant_code='TTB', name='Tenant B', subdomain='ttopt-tenant-b')
        year = AcademicYear.objects.create(name='2026-2027', start_date='2026-04-01', end_date='2027-03-31', is_active=True)

        cls_a = SchoolClass.objects.create(tenant=school_a, code='CA-TT', name='Class A', academic_year=year)
        sec_a = Section.objects.create(tenant=school_a, class_ref=cls_a, name='A', capacity=25)
        subj_a = Subject.objects.create(tenant=school_a, code='SUBJ-TTA', name='Science')
        cs_a = ClassSubject.objects.create(class_ref=cls_a, subject=subj_a, periods_per_week=1)
        teacher_a = Teacher.objects.create(tenant=school_a, employee_id='TCH-TTA', full_name='Teacher A',
                                          email='ta@code.com', phone='1', joining_date='2026-01-01')
        TeacherSubjectAssignment.objects.create(teacher=teacher_a, class_subject=cs_a, academic_year=year)
        room_a = Classroom.objects.create(tenant=school_a, name='Room A', code='RM-TTA', capacity=30, is_active=True)
        Classroom.objects.create(tenant=school_b, name='Room B', code='RM-TTB', capacity=30, is_active=True)

        cls_b = SchoolClass.objects.create(tenant=school_b, code='CB-TT', name='Class B', academic_year=year)
        Section.objects.create(tenant=school_b, class_ref=cls_b, name='A', capacity=25)

        Period.objects.create(academic_year=year, period_number=1, start_time='08:00:00', end_time='09:00:00',
                              duration_minutes=60, is_break=False, is_active=True)

        res = optimize_timetable(year.id, tenant_id=str(school_a.id), generations=10, pop_size=10)
        assert res['status'] == 'success'
        entries = list(TimetableEntry.objects.filter(academic_year=year))
        assert len(entries) == 1
        assert entries[0].section_id == sec_a.id
        assert entries[0].classroom_id == room_a.id

    def test_preview_does_not_write_to_the_database(self):
        AcademicYear = apps.get_model('education_academics', 'AcademicYear')
        SchoolClass = apps.get_model('education_academics', 'SchoolClass')
        Subject = apps.get_model('education_academics', 'Subject')
        ClassSubject = apps.get_model('education_academics', 'ClassSubject')
        Teacher = apps.get_model('education_academics', 'Teacher')
        Classroom = apps.get_model('education_academics', 'Classroom')
        Period = apps.get_model('education_academics', 'Period')
        TeacherSubjectAssignment = apps.get_model('education_academics', 'TeacherSubjectAssignment')
        Section = apps.get_model('education_academics', 'Section')
        TimetableEntry = apps.get_model('education_academics', 'TimetableEntry')

        year = AcademicYear.objects.create(name='2026-2027', start_date='2026-04-01', end_date='2027-03-31', is_active=True)
        subj = Subject.objects.create(code='SUBJ-PREV', name='History')
        cls = SchoolClass.objects.create(code='GRD-PREV', name='Grade Preview', academic_year=year)
        Section.objects.create(class_ref=cls, name='A', capacity=15)
        cs = ClassSubject.objects.create(class_ref=cls, subject=subj)
        teacher = Teacher.objects.create(employee_id='TCH-PREV', full_name='Preview Teacher',
                                         email='preview@code.com', phone='12345678', joining_date='2026-06-24')
        TeacherSubjectAssignment.objects.create(teacher=teacher, class_subject=cs, academic_year=year)
        Classroom.objects.create(name='Room Preview', code='ROOM-PREV', capacity=30, is_active=True)
        Period.objects.create(academic_year=year, period_number=1, start_time='08:00:00', end_time='09:00:00',
                              duration_minutes=60, is_break=False, is_active=True)

        res = optimize_timetable(year.id, commit=False, generations=5, pop_size=10)
        assert res['status'] == 'success' and res['committed'] is False
        assert len(res['slots']) > 0
        assert not TimetableEntry.objects.filter(academic_year_id=year.id).exists()

@pytest.mark.django_db
class TestPhase2QuizGenerator:
    def test_quiz_llm_and_fallback(self):
        res = generate_ai_quiz("Chemistry", "Acids & Bases", "medium", 2)
        assert "questions" in res
        assert len(res["questions"]) == 2
        assert res["questions"][0]["question_type"] in ["mcq", "true_false", "short_answer"]
