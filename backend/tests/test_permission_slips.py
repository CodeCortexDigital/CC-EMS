"""Permission slips and e-signature forms: building, publishing to the right families, signing once, versions, tracker."""
from datetime import timedelta

import pytest
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.user_notifications.models import Notification
from services.education.academics.models import SchoolClass
from services.education.forms.models import FormAssignment, FormResponse
from tests.safety_helpers import api, link_parent, make_student, make_user, rows, two_schools

BASE = '/api/v1/auth/forms'
QUESTIONS = [
    {'id': 'emergency', 'label': 'Emergency contact is current?', 'type': 'yes_no', 'required': True},
    {'id': 'allergy', 'label': 'Any allergies?', 'type': 'text', 'required': False},
    {'id': 'bus', 'label': 'Travel by', 'type': 'choice', 'options': ['School bus', 'Parent car'], 'required': True},
]


@pytest.fixture
def world(db):
    a, b = two_schools()
    g5 = SchoolClass.objects.create(tenant=a, name='Grade 5', code='G5')
    g6 = SchoolClass.objects.create(tenant=a, name='Grade 6', code='G6')
    ava, ben, cal = (make_student(a, current_class=g5), make_student(a, current_class=g5), make_student(a, current_class=g6))
    parents = {}
    for key, kid in (('ava', ava), ('ben', ben), ('cal', cal)):
        parents[key] = make_user(a, f'{key}.parent@a.test', 'parent')
        link_parent(parents[key], kid)
    return {'a': a, 'b': b, 'g5': g5, 'g6': g6, 'ava': ava, 'ben': ben, 'cal': cal, 'parents': parents,
            'admin': make_user(a, 'head@a.test', 'admin'), 'teacher': make_user(a, 'tim.teacher@a.test', 'teacher'),
            'admin_b': make_user(b, 'head@b.test', 'admin'), 'parent_b': make_user(b, 'p@b.test', 'parent')}


def _form(c, world, **kw):
    body = {'title': 'Zoo trip', 'body': 'I allow my child to go on the zoo trip.', 'questions': QUESTIONS, 'audience': 'classes',
            'classes': [str(world['g5'].pk)], 'due_date': str(timezone.localdate() + timedelta(days=7)), **kw}
    return c.post(f'{BASE}/templates/', body, format='json')


def _published(world, **kw):
    c = api(world['admin'])
    tid = _form(c, world, **kw).json()['id']
    assert c.post(f'{BASE}/templates/{tid}/publish/').status_code == 200
    return tid


def _assignment(world, parent_key, template_id):
    mine = rows(api(world['parents'][parent_key]).get(f'{BASE}/my/'))
    return next((m for m in mine if m['template'] == template_id), None)


def _sign(world, parent_key, aid, **kw):
    body = {'signer_name': 'Pat Parent', 'agree': True, 'decision': 'signed', 'answers': {'emergency': 'yes', 'bus': 'School bus'}, **kw}
    return api(world['parents'][parent_key]).post(f'{BASE}/my/{aid}/sign/', body, format='json')


class TestBuildingAndPublishing:
    def test_only_admins_build_teachers_read_parents_cannot_touch(self, world):
        assert _form(api(world['admin']), world).status_code == 201
        assert _form(api(world['teacher']), world).status_code == 403
        assert api(world['teacher']).get(f'{BASE}/templates/').status_code == 200
        assert api(world['parents']['ava']).get(f'{BASE}/templates/').status_code == 403
        assert api().get(f'{BASE}/templates/').status_code == 401

    def test_questions_are_checked(self, world):
        c = api(world['admin'])
        assert _form(c, world, questions=[{'label': ''}]).status_code == 400
        assert _form(c, world, questions=[{'label': 'Pick', 'type': 'choice', 'options': ['Only one']}]).status_code == 400
        assert _form(c, world, questions=[{'label': 'x', 'type': 'weird'}]).status_code == 400
        assert _form(c, world, questions=[{'id': 'a', 'label': 'x'}, {'id': 'a', 'label': 'y'}]).status_code == 400
        assert _form(c, world, classes=[]).status_code == 400

    def test_publish_sends_to_the_chosen_class_only_and_tells_parents(self, world):
        tid = _published(world)
        assert FormAssignment.objects.filter(template_id=tid).count() == 2
        assert _assignment(world, 'ava', tid) and _assignment(world, 'ben', tid)
        assert _assignment(world, 'cal', tid) is None
        assert Notification.objects.filter(recipient=world['parents']['ava'], title__icontains='form').count() == 1
        assert not Notification.objects.filter(recipient=world['parents']['cal']).exists()

    def test_everyone_audience_reaches_every_active_student(self, world):
        tid = _published(world, audience='everyone', classes=[])
        assert FormAssignment.objects.filter(template_id=tid).count() == 3

    def test_cannot_publish_twice_or_to_nobody(self, world):
        c = api(world['admin'])
        tid = _published(world)
        assert c.post(f'{BASE}/templates/{tid}/publish/').status_code == 400
        empty = SchoolClass.objects.create(tenant=world['a'], name='Grade 7', code='G7')
        nobody = _form(c, world, classes=[str(empty.pk)]).json()['id']
        assert c.post(f'{BASE}/templates/{nobody}/publish/').status_code == 400


class TestSigning:
    def test_a_parent_signs_for_their_own_child(self, world):
        tid = _published(world)
        a = _assignment(world, 'ava', tid)
        r = _sign(world, 'ava', a['id'], answers={'emergency': 'yes', 'bus': 'Parent car', 'allergy': 'Peanuts'})
        assert r.status_code == 201, r.content
        assert r.json()['status'] == 'signed' and r.json()['signer_name'] == 'Pat Parent'
        resp = FormResponse.objects.get(assignment_id=a['id'])
        assert resp.answers == {'emergency': 'yes', 'bus': 'Parent car', 'allergy': 'Peanuts'}
        assert resp.text_snapshot['body'].startswith('I allow') and resp.text_snapshot['version'] == 1
        assert AuditLog.objects.filter(user=world['parents']['ava'], resource_type='forms/signature').exists()

    def test_a_signature_is_final(self, world):
        tid = _published(world)
        a = _assignment(world, 'ava', tid)
        assert _sign(world, 'ava', a['id']).status_code == 201
        assert _sign(world, 'ava', a['id'], signer_name='Someone Else').status_code == 400
        assert FormResponse.objects.filter(assignment_id=a['id']).count() == 1
        assert api(world['parents']['ava']).patch(f'{BASE}/my/{a["id"]}/', {'status': 'pending'}, format='json').status_code == 405

    def test_a_parent_cannot_sign_for_another_family(self, world):
        tid = _published(world)
        bens = _assignment(world, 'ben', tid)
        assert _sign(world, 'ava', bens['id']).status_code == 404
        assert _sign(world, 'cal', bens['id']).status_code == 404
        assert not FormResponse.objects.exists()

    def test_needs_the_typed_name_the_tick_box_and_required_answers(self, world):
        tid = _published(world)
        aid = _assignment(world, 'ava', tid)['id']
        assert _sign(world, 'ava', aid, signer_name='  ').status_code == 400
        assert _sign(world, 'ava', aid, agree=False).status_code == 400
        assert _sign(world, 'ava', aid, answers={'bus': 'School bus'}).status_code == 400          # missing required yes/no
        assert _sign(world, 'ava', aid, answers={'emergency': 'maybe', 'bus': 'School bus'}).status_code == 400
        assert _sign(world, 'ava', aid, answers={'emergency': 'yes', 'bus': 'Rocket'}).status_code == 400
        assert _sign(world, 'ava', aid, decision='later').status_code == 400
        assert not FormResponse.objects.exists()

    def test_a_family_can_decline_without_answering_everything(self, world):
        tid = _published(world)
        a = _assignment(world, 'ben', tid)
        r = _sign(world, 'ben', a['id'], decision='declined', answers={})
        assert r.status_code == 201 and r.json()['status'] == 'declined'

    def test_only_parents_sign(self, world):
        tid = _published(world)
        aid = _assignment(world, 'ava', tid)['id']
        for who in ('admin', 'teacher'):
            assert api(world[who]).post(f'{BASE}/my/{aid}/sign/', {'signer_name': 'x', 'agree': True}, format='json').status_code == 403


class TestVersions:
    def test_wording_is_locked_once_families_have_signed(self, world):
        c = api(world['admin'])
        tid = _published(world)
        assert c.patch(f'{BASE}/templates/{tid}/', {'body': 'New wording'}, format='json').status_code == 200  # nobody has signed yet
        _sign(world, 'ava', _assignment(world, 'ava', tid)['id'])
        locked = c.patch(f'{BASE}/templates/{tid}/', {'body': 'Sneaky change'}, format='json')
        assert locked.status_code == 400 and 'new version' in str(locked.json()).lower()
        assert c.patch(f'{BASE}/templates/{tid}/', {'due_date': str(timezone.localdate() + timedelta(days=30))}, format='json').status_code == 200

    def test_new_version_archives_the_old_one_and_keeps_what_was_signed(self, world):
        c = api(world['admin'])
        tid = _published(world)
        aid = _assignment(world, 'ava', tid)['id']
        _sign(world, 'ava', aid)
        new = c.post(f'{BASE}/templates/{tid}/new_version/')
        assert new.status_code == 201 and new.json()['version'] == 2 and new.json()['status'] == 'draft'
        c.patch(f'{BASE}/templates/{new.json()["id"]}/', {'body': 'Updated wording for the trip'}, format='json')
        assert c.get(f'{BASE}/templates/{tid}/').json()['status'] == 'archived'
        assert FormResponse.objects.get(assignment_id=aid).text_snapshot['body'].startswith('I allow')
        assert c.post(f'{BASE}/templates/{new.json()["id"]}/publish/').status_code == 200
        # an archived form can no longer be signed
        assert _sign(world, 'ben', _assignment(world, 'ben', tid)['id']).status_code == 400


class TestTracker:
    def test_counts_rows_and_reminders_only_reach_unsigned_families(self, world):
        c = api(world['admin'])
        tid = _published(world)
        _sign(world, 'ava', _assignment(world, 'ava', tid)['id'])
        t = c.get(f'{BASE}/templates/{tid}/tracker/').json()
        assert t['counts'] == {'total': 2, 'signed': 1, 'declined': 0, 'pending': 1}
        assert {r['student_name']: r['status'] for r in t['rows']} == {world['ava'].full_name: 'signed', world['ben'].full_name: 'pending'}
        assert [r['student_name'] for r in c.get(f'{BASE}/templates/{tid}/tracker/?status=pending').json()['rows']] == [world['ben'].full_name]
        Notification.objects.all().delete()
        assert c.post(f'{BASE}/templates/{tid}/remind/').json()['reminded'] == 1
        assert Notification.objects.filter(recipient=world['parents']['ben'], title__icontains='reminder').count() == 1
        assert not Notification.objects.filter(recipient=world['parents']['ava']).exists()
        assert api(world['teacher']).post(f'{BASE}/templates/{tid}/remind/').status_code == 403

    def test_csv_export_has_a_row_per_student_with_answers(self, world):
        c = api(world['admin'])
        tid = _published(world)
        _sign(world, 'ava', _assignment(world, 'ava', tid)['id'], answers={'emergency': 'yes', 'bus': 'School bus'})
        text = c.get(f'{BASE}/templates/{tid}/export/').content.decode()
        lines = text.strip().splitlines()
        assert lines[0].startswith('Student,Class,Status,Signed by,Signed at,Emergency contact is current?')
        assert len(lines) == 3 and any('Signed' in l and 'Pat Parent' in l and 'School bus' in l for l in lines)


class TestIsolation:
    def test_another_school_sees_and_signs_nothing(self, world):
        tid = _published(world)
        aid = _assignment(world, 'ava', tid)['id']
        other = api(world['admin_b'])
        assert rows(other.get(f'{BASE}/templates/')) == []
        assert other.get(f'{BASE}/templates/{tid}/').status_code == 404
        assert other.post(f'{BASE}/templates/{tid}/publish/').status_code == 404
        assert rows(api(world['parent_b']).get(f'{BASE}/my/')) == []
        assert api(world['parent_b']).post(f'{BASE}/my/{aid}/sign/', {'signer_name': 'x', 'agree': True}, format='json').status_code == 404
