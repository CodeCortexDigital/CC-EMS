"""The risk scoring says plainly what it is: a model card, a record of each scan, and a first look at who gets flagged."""
import pytest

from services.analytics.ai_views import fairness_snapshot
from services.analytics.model_card import MODEL_CARD
from services.analytics.models import RiskScanRun
from tests.safety_helpers import api, make_user, two_schools

CARD = '/api/v1/ai/risk-model-card/'
SETTINGS = '/api/v1/ai/settings/'


@pytest.fixture
def world(db):
    a, b = two_schools()
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin'),
            'teacher': make_user(a, 'tim.teacher@a.test', 'teacher'), 'parent': make_user(a, 'mom@a.test', 'parent')}


def test_the_card_states_what_the_scores_are_and_are_not():
    text = ' '.join([MODEL_CARD['summary'], MODEL_CARD['training_data'], *MODEL_CARD['limits']])
    assert 'not learned from recorded outcomes' in text and 'No accuracy figures' in text
    assert {'Family income', 'Number of siblings', 'Gender'} <= set(MODEL_CARD['not_used'])
    assert {m['name'] for m in MODEL_CARD['models']} == {'Dropout risk', 'Fee-default risk', 'Grade band', 'Attendance anomalies'}


def test_the_inputs_the_card_lists_are_the_inputs_the_code_uses():
    try:
        from services.analytics import ai_views
        if not ai_views.RISK_ML_AVAILABLE:
            pytest.skip('risk-scoring packages are not installed here')
        import predictions.dropout_fee_model as dfm
    except ImportError:
        pytest.skip('risk-scoring packages are not installed here')
    assert dfm.FEE_FEATURES == ['unpaid_ratio'] and dfm.DROPOUT_FEATURES == ['attendance_rate', 'exam_avg', 'behavior_concerns']
    assert 'income' not in dfm.FEE_FEATURES and 'siblings' not in dfm.FEE_FEATURES
    assert f'{int(dfm.FEE_RULE_OVERDUE_SHARE * 100)}%' in ' '.join(m['rule'] for m in MODEL_CARD['models'])
    assert str(dfm.DROPOUT_RULE_THRESHOLD) in ' '.join(m['rule'] for m in MODEL_CARD['models'])


def test_staff_can_read_the_card_and_it_has_no_run_before_a_scan(world):
    res = api(world['admin']).get(CARD)
    assert res.status_code == 200 and res.json()['latest_run'] is None and res.json()['limits']
    assert api(world['parent']).get(CARD).status_code == 403


def test_it_shows_this_schools_latest_scan_only(world):
    RiskScanRun.objects.create(tenant=world['a'], students_scored=42, details={'level_counts': {'high': 3}}, fairness={'gender': {'groups': []}})
    RiskScanRun.objects.create(tenant=world['b'], students_scored=7)
    mine = api(world['admin']).get(CARD).json()['latest_run']
    assert mine['students_scored'] == 42 and mine['details']['level_counts'] == {'high': 3}
    assert api(world['admin_b']).get(CARD).json()['latest_run']['students_scored'] == 7


def test_the_card_goes_away_with_the_ai_switch(world):
    assert api(world['admin']).get(CARD).status_code == 200
    api(world['admin']).put(SETTINGS, {'ai_enabled': False}, format='json')
    assert api(world['admin']).get(CARD).status_code == 403


def test_the_flag_rate_check_hides_small_groups_and_reports_the_ratio():
    rows = ([{'gender': 'female', 'class': '5A', 'flagged': i < 5} for i in range(20)]
            + [{'gender': 'male', 'class': '5A', 'flagged': i < 10} for i in range(20)]
            + [{'gender': 'other', 'class': '5B', 'flagged': True} for _ in range(3)])
    out = fairness_snapshot(rows)
    assert [g['group'] for g in out['gender']['groups']] == ['female', 'male'] and out['gender']['hidden_small_groups'] == 1
    assert out['gender']['groups'][0]['flag_rate'] == 25.0 and out['gender']['groups'][1]['flag_rate'] == 50.0
    assert out['gender']['lowest_to_highest_rate'] == 0.5
    assert out['class']['lowest_to_highest_rate'] is None          # only one class is large enough to show
