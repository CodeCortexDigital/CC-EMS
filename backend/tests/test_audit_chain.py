"""The tamper-evident trail for AI and risk-review decisions: chained, protected, checked, and never optional."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from services.core.audit import chain
from services.core.audit.models import AuditLog, ProtectedAuditError
from services.core.tenants.signup import create_school_with_admin


@pytest.fixture
def school(db):
    return create_school_with_admin(school_name='Alder Academy', admin_email='head@alder.test', admin_name='Head', password='Sturdy-Pass-91x')


def _write(school, admin, n=3):
    return [chain.append(user=admin, school=school, action='UPDATE', resource_type='ai.action.send_fee_reminder',
                         new_data={'status': s}) for s in ('requested', 'approved', 'executed')[:n]]


def test_records_follow_one_another_and_verify(school):
    s, admin = school
    rows = _write(s, admin)
    assert [r.seq for r in rows] == [1, 2, 3] and rows[1].prev_hash == rows[0].entry_hash and rows[0].prev_hash == ''
    assert rows[0].new_data['actor'] == 'head@alder.test'
    result = chain.verify()
    assert result['ok'] and result['records'] == 3 and result['heads'][str(s.pk)] == rows[2].entry_hash


def test_each_school_has_its_own_chain(school):
    s, admin = school
    other, other_admin = create_school_with_admin(school_name='Birch', admin_email='head@birch.test', admin_name='B', password='Sturdy-Pass-91x')
    _write(s, admin, 2)
    _write(other, other_admin, 2)
    assert chain.verify()['ok'] and chain.verify()['chains'] == 2
    assert [r.seq for r in AuditLog.objects.filter(chain=str(other.pk)).order_by('seq')] == [1, 2]


def test_a_changed_record_is_found(school):
    s, admin = school
    rows = _write(s, admin)
    AuditLog._base_manager.filter(pk=rows[1].pk).update(new_data={'status': 'rejected', 'actor': 'head@alder.test'})   # straight to the database
    result = chain.verify()
    assert not result['ok'] and 'record 2' in result['problems'][0] and 'changed' in result['problems'][0]
    with pytest.raises(CommandError):
        call_command('verify_audit_chain')


def test_a_removed_record_is_found_in_the_middle_and_at_the_end(school):
    s, admin = school
    rows = _write(s, admin)
    AuditLog._base_manager.filter(pk=rows[1].pk).delete()
    assert any('missing' in p for p in chain.verify()['problems'])
    AuditLog._base_manager.filter(pk=rows[2].pk).delete()
    assert any('newest record' in p for p in chain.verify()['problems'])


def test_the_application_cannot_change_or_delete_a_protected_record(school):
    s, admin = school
    row = _write(s, admin, 1)[0]
    with pytest.raises(ProtectedAuditError):
        AuditLog.objects.filter(pk=row.pk).delete()
    with pytest.raises(ProtectedAuditError):
        AuditLog.objects.filter(pk=row.pk).update(action='DELETE')
    row.new_data = {'status': 'forged'}
    with pytest.raises(ProtectedAuditError):
        row.save()
    with pytest.raises(ProtectedAuditError):
        row.delete()
    assert chain.verify()['ok']


def test_routine_audit_rows_are_still_removable_and_cleanup_keeps_decision_records(school):
    s, admin = school
    row = _write(s, admin, 1)[0]
    routine = AuditLog.objects.create(user=admin, school=s, action='VIEW', resource_type='students')
    AuditLog._base_manager.filter(pk__in=[row.pk, routine.pk]).update(timestamp='2020-01-01T00:00:00Z')
    call_command('cleanup_audit_logs', '--days', '30')
    assert AuditLog.objects.filter(pk=row.pk).exists() and not AuditLog.objects.filter(pk=routine.pk).exists()


def test_deleting_the_user_does_not_break_the_chain(school):
    s, admin = school
    _write(s, admin)
    admin.delete()
    assert chain.verify()['ok']


def test_a_record_that_cannot_be_written_raises(school, monkeypatch):
    s, admin = school
    monkeypatch.setattr(AuditLog.objects, 'create', lambda **kw: (_ for _ in ()).throw(RuntimeError('disk full')), raising=False)
    with pytest.raises(chain.AuditWriteError):
        chain.append(user=admin, school=s, action='UPDATE', resource_type='ai.action.x', new_data={})
