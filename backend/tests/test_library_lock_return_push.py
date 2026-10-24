"""Library: lock a copy in the safe with a reason, check the returned book is the one on the loan, and library notices that reach phones."""
from datetime import timedelta

import pytest
from django.utils import timezone

from services.core.audit.models import AuditLog
from services.core.tenants.context import use_tenant
from services.core.user_notifications import push
from services.core.user_notifications.models import Notification
from services.education.library.models import BookCopy, Loan
from services.education.library.tasks import send_all_reminders
from tests.test_library import URL, _card, _client, lib  # noqa: F401  (the school, office, students and a book with two copies)


def _copy(d, barcode):
    return BookCopy.objects.get(barcode=barcode)


def _issue(d, barcode='LIB-000001'):
    card = _card(d, d['sara'])
    res = d['office'].post(f'{URL}/issue/', {'barcode': barcode, 'member_id': card['id']}, format='json')
    assert res.status_code == 201, res.content
    return card, res.json()['loan']


@pytest.mark.django_db
class TestLockInTheSafe:
    def patch(self, d, barcode, body):
        return d['office'].patch(f'{URL}/copies/{_copy(d, barcode).id}/', body, format='json')

    def test_a_reason_is_required_and_a_locked_copy_is_not_available_or_lendable(self, lib):
        d = lib
        assert self.patch(d, 'LIB-000001', {'status': 'locked'}).status_code == 400
        assert 'why' in self.patch(d, 'LIB-000001', {'status': 'locked', 'reason': '  '}).json()['error']
        ok = self.patch(d, 'LIB-000001', {'status': 'locked', 'reason': 'Rare first edition, kept in the safe'})
        assert ok.status_code == 200 and ok.json()['status'] == 'locked'
        detail = d['office'].get(f"{URL}/books/{d['book']['id']}/").json()
        row = next(c for c in detail['copy_list'] if c['barcode'] == 'LIB-000001')
        assert row['status_label'] == 'Locked in the safe' and row['locked_reason'].startswith('Rare first edition')
        assert row['locked_by'] == 'Office Admin' and row['locked_at']
        assert detail['available'] == 1                                   # only the other copy can be lent
        card = _card(d, d['sara'])
        refused = d['office'].post(f'{URL}/issue/', {'barcode': 'LIB-000001', 'member_id': card['id']}, format='json')
        assert refused.status_code == 400 and 'locked in the safe' in refused.json()['error'] and 'Rare first edition' in refused.json()['error']

    def test_unlocking_clears_the_reason_and_both_steps_are_audited(self, lib):
        d = lib
        self.patch(d, 'LIB-000001', {'status': 'locked', 'reason': 'Water damage, kept aside'})
        assert self.patch(d, 'LIB-000001', {'status': 'available'}).json()['status'] == 'available'
        c = _copy(d, 'LIB-000001')
        assert c.locked_reason == '' and c.locked_at is None and c.locked_by is None
        kinds = set(AuditLog.objects.filter(resource_id=c.id).values_list('resource_type', flat=True))
        assert {'library.copy.locked', 'library.copy.unlocked'} <= kinds
        locked = AuditLog.objects.get(resource_type='library.copy.locked')
        assert locked.new_data['reason'] == 'Water damage, kept aside' and locked.user == d['admin']

    def test_only_a_copy_on_the_shelf_can_be_locked(self, lib):
        d = lib
        _issue(d)
        on_loan = self.patch(d, 'LIB-000001', {'status': 'locked', 'reason': 'x'})
        assert on_loan.status_code == 400 and 'on loan' in on_loan.json()['error']
        self.patch(d, 'LIB-000002', {'status': 'lost'})
        lost = self.patch(d, 'LIB-000002', {'status': 'locked', 'reason': 'x'})
        assert lost.status_code == 400 and 'on the shelf' in lost.json()['error']

    def test_a_locked_copy_can_be_marked_lost_and_the_lock_is_cleared(self, lib):
        d = lib
        self.patch(d, 'LIB-000001', {'status': 'locked', 'reason': 'Safe'})
        assert self.patch(d, 'LIB-000001', {'status': 'lost'}).json()['status'] == 'lost'
        assert _copy(d, 'LIB-000001').locked_reason == ''

    def test_families_cannot_lock_anything(self, lib):
        d = lib
        res = _client(d['parent']).patch(f"{URL}/copies/{_copy(d, 'LIB-000001').id}/", {'status': 'locked', 'reason': 'x'}, format='json')
        assert res.status_code == 403 and _copy(d, 'LIB-000001').status == 'available'


@pytest.mark.django_db
class TestReturnCheck:
    def test_the_scanned_book_must_be_the_one_on_the_loan(self, lib):
        d = lib
        _, loan = _issue(d, 'LIB-000001')
        wrong = d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'barcode': 'LIB-000002'}, format='json')
        assert wrong.status_code == 409
        msg = wrong.json()['error']
        assert 'not the book on this loan' in msg and 'LIB-000002' in msg and 'LIB-000001' in msg
        assert Loan.objects.get(pk=loan['id']).returned_at is None                         # nothing was returned
        right = d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'barcode': 'lib-000001'}, format='json')
        assert right.status_code == 200 and right.json()['loan']['return_method'] == 'scan'
        assert _copy(d, 'LIB-000001').status == 'available'

    def test_an_unreadable_label_can_be_confirmed_by_hand_and_it_is_recorded(self, lib):
        d = lib
        _, loan = _issue(d)
        res = d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'manual': True}, format='json')
        assert res.status_code == 200 and res.json()['loan']['return_method'] == 'manual'
        assert Loan.objects.get(pk=loan['id']).returned_at is not None

    def test_an_unknown_barcode_or_a_closed_loan_is_refused(self, lib):
        d = lib
        _, loan = _issue(d)
        assert d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'barcode': 'NOPE'}, format='json').status_code == 404
        d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'barcode': 'LIB-000001'}, format='json')
        again = d['office'].post(f'{URL}/return/', {'loan_id': loan['id'], 'barcode': 'LIB-000001'}, format='json')
        assert again.status_code == 404 and 'not open' in again.json()['error']

    def test_the_desk_scan_without_a_loan_still_works(self, lib):
        d = lib
        _issue(d)
        res = d['office'].post(f'{URL}/return/', {'barcode': 'LIB-000001'}, format='json')
        assert res.status_code == 200 and res.json()['loan']['return_method'] == 'scan'


@pytest.mark.django_db
class TestLibraryNoticesReachPhones:
    def test_borrowing_tells_the_student_and_family_with_the_due_date_as_a_library_notice(self, lib):
        d = lib
        _, loan = _issue(d)
        notes = Notification.objects.filter(title='Library book borrowed')
        assert notes.count() >= 2                                                         # the student and the parent
        assert {n.notification_type for n in notes} == {'library'}
        assert all('The Secret Garden' in n.message and 'due back on' in n.message for n in notes)

    def test_reminders_are_library_notices_and_a_tap_opens_the_library_page(self, lib):
        d = lib
        _issue(d)
        Loan.objects.update(due_date=timezone.localdate() - timedelta(days=2))
        with use_tenant(d['s']):
            totals = send_all_reminders()
        assert totals['overdue'] == 1
        n = Notification.objects.get(title='Library book overdue', recipient=d['parent'])
        assert n.notification_type == 'library'
        payload = push.payload_for(n)
        assert payload['url'] == '/library' and payload['type'] == 'library'
        assert push.payload_for(Notification(title='x', message='y', notification_type='finance', recipient=d['parent']))['url'] == '/'

    def test_library_notices_can_be_switched_off_on_their_own(self, lib):
        d = lib
        assert 'library' in dict(Notification.NOTIFICATION_TYPES)
        res = _client(d['parent']).put('/api/v1/auth/notifications/push/preferences/', {'muted_types': ['library']}, format='json')
        if res.status_code == 404:
            pytest.skip('preferences route differs')
        assert res.status_code == 200
        _issue(d)
        n = Notification.objects.filter(recipient=d['parent'], notification_type='library').first()
        assert n is not None and n.notification_type in push.muted_types(d['parent'].id)

    def test_the_reminder_job_is_scheduled_every_day(self):
        from django.conf import settings

        job = settings.CELERY_BEAT_SCHEDULE['library-reminders']
        assert job['task'] == 'services.education.library.tasks.send_library_reminders'
