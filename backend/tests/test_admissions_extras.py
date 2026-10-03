"""Admissions extras: the waiting list and seat offers, tours and interviews, the document checklist, the application fee."""
import json
from datetime import timedelta
from unittest import mock

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from services.core.tenants.context import use_tenant
from services.education.admissions import fee as fees
from services.education.admissions.models import Applicant, Application, ApplicationFee, Offer, TourBooking, TourSlot, WaitlistEntry
from services.education.finance.payments import stripe_gateway
from services.education.students.models import StudentDocument
from tests.conftest import ClassFactory
from tests.safety_helpers import api, make_user, rows, two_schools

BASE = '/api/v1/auth/admissions'
YEAR = '2026-2027'


@pytest.fixture
def world(db):
    a, b = two_schools()
    ClassFactory(school=a, name='Grade 5')
    return {'a': a, 'b': b, 'admin': make_user(a, 'head@a.test', 'admin'), 'admin_b': make_user(b, 'head@b.test', 'admin')}


_n = iter(range(1, 10_000))


def mk(school, name, grade='Grade 5', status='pending', sibling='', year=YEAR):
    i = next(_n)
    with use_tenant(school):
        applicant = Applicant.objects.create(tenant=school, full_name=name, email=f'family{i}@example.test', gender='F',
                                             applying_for_class=grade, academic_year=year, sibling_at_school=sibling)
        return Application.objects.create(applicant=applicant, academic_year=year, status=status)


def creds(app):
    return {'no': app.application_no, 'token': app.tracking_token}


def set_status(admin, app, status):
    return admin.post(f'{BASE}/applications/{app.pk}/update-status/', {'status': status, 'notify': False}, format='json')


def config(admin, capacity=1, grade='Grade 5', **kw):
    r = admin.post(f'{BASE}/waitlist-configs/', {'class_name': grade, 'academic_year': YEAR, 'capacity': capacity, **kw}, format='json')
    assert r.status_code == 201, r.content
    return r.json()


def add(admin, cfg, app, **kw):
    return admin.post(f'{BASE}/waitlist-configs/{cfg["id"]}/add/', {'application': str(app.pk), **kw}, format='json')


def open_offers():
    with use_tenant(None):
        return list(Offer.objects.filter(status='offered').select_related('entry__application__applicant'))


def answer(app, decision):
    return api().post(f'{BASE}/public/offer/', {**creds(app), 'decision': decision}, format='json')


class TestWaitingList:
    def test_the_line_moves_offer_by_offer_and_never_over_fills(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=1)
        holder = mk(world['a'], 'Holder', status='approved')
        alice, bella, cara = mk(world['a'], 'Alice'), mk(world['a'], 'Bella', sibling='Brother Ben, Grade 7'), mk(world['a'], 'Cara')
        for app, kw in ((alice, {}), (bella, {}), (cara, {'staff_child': True})):
            assert add(admin, cfg, app, **kw).status_code == 201

        # line order: sibling first, then staff child, then whoever joined first
        entries = admin.get(f'{BASE}/waitlist-configs/{cfg["id"]}/entries/').json()
        assert [e['student_name'] for e in entries['entries']] == ['Bella', 'Cara', 'Alice']
        assert [e['position'] for e in entries['entries']] == [1, 2, 3]
        assert entries['config']['seats_left'] == 0 and not open_offers()           # the seat is taken

        # the seat holder withdraws: the front of the line is offered it, and only one offer exists
        assert set_status(admin, holder, 'withdrawn').status_code == 200
        assert [o.entry.application.applicant.full_name for o in open_offers()] == ['Bella']
        assert any('place has opened' in m.body for m in mail.outbox)

        # Bella declines: Cara is offered it
        assert answer(bella, 'decline').status_code == 200
        assert [o.entry.application.applicant.full_name for o in open_offers()] == ['Cara']

        # Cara does not answer in time: the offer expires and Alice is offered the seat
        Offer.objects.filter(status='offered').update(expires_at=timezone.now() - timedelta(hours=1))
        call_command('admissions_daily')
        assert [o.entry.application.applicant.full_name for o in open_offers()] == ['Alice']
        assert answer(cara, 'accept').status_code == 400                                  # too late

        # Alice accepts: she is approved, the line is empty, the grade is full
        r = answer(alice, 'accept')
        assert r.status_code == 200, r.content
        with use_tenant(None):
            assert Application.objects.get(pk=alice.pk).status == 'approved'
        final = admin.get(f'{BASE}/waitlist-configs/{cfg["id"]}/entries/').json()
        assert final['entries'] == [] and final['config']['seats_left'] == 0 and final['config']['seats_taken'] == 1

    def test_more_seats_means_offers_go_out_straight_away(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=1)
        mk(world['a'], 'Holder', status='approved')
        first, second = mk(world['a'], 'First'), mk(world['a'], 'Second')
        add(admin, cfg, first)
        add(admin, cfg, second)
        assert not open_offers()
        assert admin.patch(f'{BASE}/waitlist-configs/{cfg["id"]}/', {'capacity': 3}, format='json').status_code == 200
        assert {o.entry.application.applicant.full_name for o in open_offers()} == {'First', 'Second'}
        # cutting capacity never creates negative seats
        admin.patch(f'{BASE}/waitlist-configs/{cfg["id"]}/', {'capacity': 0}, format='json')
        assert admin.get(f'{BASE}/waitlist-configs/{cfg["id"]}/').json()['seats_left'] == 0

    def test_an_offer_can_only_be_answered_once_and_only_with_the_right_code(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=1)
        app = mk(world['a'], 'Alice')
        add(admin, cfg, app)                                           # a free seat: offered at once
        assert api().post(f'{BASE}/public/offer/', {'no': app.application_no, 'token': 'wrong', 'decision': 'accept'}, format='json').status_code == 404
        assert answer(app, 'maybe').status_code == 400
        assert answer(app, 'accept').status_code == 200
        assert answer(app, 'accept').status_code == 400                # nothing open any more
        assert api().get(f'{BASE}/public/offer/', creds(app)).json()['offer'] is None

    def test_staff_can_withdraw_an_open_offer_and_the_next_family_gets_it(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=1)
        mk(world['a'], 'Holder', status='approved')
        a1, a2 = mk(world['a'], 'One'), mk(world['a'], 'Two')
        add(admin, cfg, a1); add(admin, cfg, a2)
        holder = Application.objects.get(applicant__full_name='Holder')
        set_status(admin, holder, 'rejected')
        offer = open_offers()[0]
        assert admin.post(f'{BASE}/offers/{offer.pk}/withdraw/').status_code == 200
        assert [o.entry.application.applicant.full_name for o in open_offers()] == ['Two']

    def test_who_may_join_the_list(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=0)
        assert add(admin, cfg, mk(world['a'], 'Wrong grade', grade='Grade 7')).status_code == 400
        assert add(admin, cfg, mk(world['a'], 'Wrong year', year='2030-2031')).status_code == 400
        assert add(admin, cfg, mk(world['a'], 'Gone', status='withdrawn')).status_code == 400
        assert add(admin, cfg, mk(world['a'], 'Enrolled', status='enrolled')).status_code == 400
        assert add(admin, cfg, mk(world['a'], 'Fine')).status_code == 201

    def test_a_held_application_cannot_join_or_be_reviewed(self, world):
        admin = api(world['admin'])
        cfg = config(admin, capacity=2)
        app = mk(world['a'], 'Unpaid')
        with use_tenant(world['a']):
            ApplicationFee.objects.create(application=app, amount='25.00')
        assert add(admin, cfg, app).status_code == 400
        assert set_status(admin, app, 'reviewing').status_code == 400
        assert set_status(admin, app, 'withdrawn').status_code == 200   # leaving is always allowed

    def test_only_admins_and_only_their_own_school(self, world):
        admin, other = api(world['admin']), api(world['admin_b'])
        cfg = config(admin, capacity=1)
        app = mk(world['a'], 'Alice')
        add(admin, cfg, app)
        assert api(make_user(world['a'], 'tim.teacher@a.test', 'teacher')).get(f'{BASE}/waitlist-configs/').status_code == 403
        assert rows(other.get(f'{BASE}/waitlist-configs/')) == [] and rows(other.get(f'{BASE}/offers/')) == []
        assert other.get(f'{BASE}/waitlist-configs/{cfg["id"]}/').status_code == 404
        assert add(other, cfg, app).status_code == 404
        # a second grade/year entry for the same pair is refused
        assert admin.post(f'{BASE}/waitlist-configs/', {'class_name': 'Grade 5', 'academic_year': YEAR, 'capacity': 3}, format='json').status_code == 400


def slot(admin, kind='tour', hours=48, capacity=1, **kw):
    start = timezone.now() + timedelta(hours=hours)
    r = admin.post(f'{BASE}/tour-slots/', {'kind': kind, 'starts_at': start.isoformat(), 'ends_at': (start + timedelta(hours=1)).isoformat(),
                                           'capacity': capacity, 'location': 'Front office', **kw}, format='json')
    assert r.status_code == 201, r.content
    return r.json()


def book(app, slot_id):
    return api().post(f'{BASE}/public/tours/', {**creds(app), 'slot': slot_id}, format='json')


class TestTours:
    def test_booking_respects_capacity_and_frees_the_seat_on_cancel(self, world):
        admin = api(world['admin'])
        s = slot(admin, capacity=1)
        f1, f2 = mk(world['a'], 'Family One'), mk(world['a'], 'Family Two')
        listed = api().get(f'{BASE}/public/tours/', {**creds(f1), 'kind': 'tour'}).json()
        assert [x['id'] for x in listed['slots']] == [s['id']] and listed['slots'][0]['seats_left'] == 1
        first = book(f1, s['id'])
        assert first.status_code == 201
        assert book(f2, s['id']).status_code == 400                                       # full
        assert api().get(f'{BASE}/public/tours/', {**creds(f2), 'kind': 'tour'}).json()['slots'] == []
        assert api().post(f'{BASE}/public/tours/cancel/', {**creds(f1), 'booking': first.json()['id']}, format='json').status_code == 200
        assert book(f2, s['id']).status_code == 201
        assert any('booked' in m.subject.lower() for m in mail.outbox)

    def test_one_booking_of_each_kind_and_interviews_set_the_interview_date(self, world):
        admin = api(world['admin'])
        t1, t2, interview = slot(admin, hours=30), slot(admin, hours=50), slot(admin, kind='interview', hours=70)
        fam = mk(world['a'], 'Family')
        assert book(fam, t1['id']).status_code == 201
        assert book(fam, t2['id']).status_code == 400                                     # already has a tour
        booked = book(fam, interview['id'])
        assert booked.status_code == 201
        assert Application.objects.get(pk=fam.pk).interview_date is not None
        api().post(f'{BASE}/public/tours/cancel/', {**creds(fam), 'booking': booked.json()['id']}, format='json')
        assert Application.objects.get(pk=fam.pk).interview_date is None

    def test_past_closed_and_unknown_times_cannot_be_booked(self, world):
        admin = api(world['admin'])
        fam = mk(world['a'], 'Family')
        closed = slot(admin, is_open=False)
        assert book(fam, closed['id']).status_code == 400
        with use_tenant(world['a']):
            past = TourSlot.objects.create(kind='tour', starts_at=timezone.now() - timedelta(hours=2), ends_at=timezone.now() - timedelta(hours=1))
        assert book(fam, str(past.pk)).status_code == 400
        assert book(fam, 'not-a-slot').status_code == 400
        assert api().post(f'{BASE}/public/tours/', {'no': fam.application_no, 'token': 'bad', 'slot': closed['id']}, format='json').status_code == 404

    def test_admin_rules_for_slots(self, world):
        admin = api(world['admin'])
        s = slot(admin, capacity=2)
        book(mk(world['a'], 'One'), s['id']); book(mk(world['a'], 'Two'), s['id'])
        assert admin.delete(f'{BASE}/tour-slots/{s["id"]}/').status_code == 400           # families have booked it
        assert admin.patch(f'{BASE}/tour-slots/{s["id"]}/', {'capacity': 1}, format='json').status_code == 400
        assert admin.post(f'{BASE}/tour-slots/', {'kind': 'tour', 'starts_at': timezone.now().isoformat(),
                                                  'ends_at': (timezone.now() - timedelta(hours=1)).isoformat()}, format='json').status_code == 400
        bookings = rows(admin.get(f'{BASE}/tour-bookings/?slot={s["id"]}'))
        assert len(bookings) == 2
        assert admin.post(f'{BASE}/tour-bookings/{bookings[0]["id"]}/cancel/').status_code == 200
        assert admin.get(f'{BASE}/tour-slots/{s["id"]}/').json()['seats_left'] == 1

    def test_reminder_goes_out_once_the_day_before(self, world):
        admin = api(world['admin'])
        soon, later = slot(admin, hours=20), slot(admin, hours=100)
        a, b = mk(world['a'], 'Soon family'), mk(world['a'], 'Later family')
        book(a, soon['id']); book(b, later['id'])
        mail.outbox.clear()
        call_command('admissions_daily')
        assert [m.to for m in mail.outbox if 'Reminder' in m.subject] == [[a.applicant.email]]
        mail.outbox.clear()
        call_command('admissions_daily')
        assert not [m for m in mail.outbox if 'Reminder' in m.subject]
        assert TourBooking.objects.filter(reminder_sent_at__isnull=False).count() == 1

    def test_other_schools_see_no_slots(self, world):
        slot(api(world['admin']))
        assert rows(api(world['admin_b']).get(f'{BASE}/tour-slots/')) == []


def pdf(name='birth.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


def upload(app, doc_type='Birth certificate', file=None):
    return api().post(f'{BASE}/public/documents/', {**creds(app), 'doc_type': doc_type, 'file': file or pdf()}, format='multipart')


def states(admin, app):
    return {i['name']: i['state'] for i in admin.get(f'{BASE}/applications/{app.pk}/checklist/').json()['items']}


class TestDocumentChecklist:
    def test_missing_uploaded_received_and_sent_again(self, world):
        admin = api(world['admin'])
        app = mk(world['a'], 'Family')
        assert states(admin, app) == {'Birth certificate': 'missing', 'Recent report card': 'missing', 'Passport-size photo': 'missing'}
        assert upload(app).status_code == 201
        assert states(admin, app)['Birth certificate'] == 'uploaded'
        doc_id = admin.get(f'{BASE}/applications/{app.pk}/checklist/').json()['items'][0]['document']['id']

        assert admin.post(f'{BASE}/applications/{app.pk}/documents/{doc_id}/review/', {'status': 'redo'}, format='json').status_code == 400  # needs a note
        mail.outbox.clear()
        redo = admin.post(f'{BASE}/applications/{app.pk}/documents/{doc_id}/review/', {'status': 'redo', 'note': 'The scan is blurry'}, format='json')
        assert redo.status_code == 200 and states(admin, app)['Birth certificate'] == 'redo'
        assert 'blurry' in mail.outbox[-1].body

        assert upload(app, file=pdf('birth2.pdf')).status_code == 201                      # sent again: replaces the old one
        assert states(admin, app)['Birth certificate'] == 'uploaded'
        assert ApplicationDocumentCount(app) == 1
        new_id = admin.get(f'{BASE}/applications/{app.pk}/checklist/').json()['items'][0]['document']['id']
        assert admin.post(f'{BASE}/applications/{app.pk}/documents/{new_id}/review/', {'status': 'received'}, format='json').status_code == 200
        assert states(admin, app)['Birth certificate'] == 'received'
        assert upload(app).status_code == 400                                              # already received

    def test_only_the_documents_the_school_asked_for_with_the_right_code(self, world):
        app = mk(world['a'], 'Family')
        assert upload(app, doc_type='Random thing').status_code == 400
        assert api().post(f'{BASE}/public/documents/', {**creds(app), 'doc_type': 'Birth certificate'}, format='multipart').status_code == 400
        bad_code = {'no': app.application_no, 'token': 'nope', 'doc_type': 'Birth certificate', 'file': pdf()}
        assert api().post(f'{BASE}/public/documents/', bad_code, format='multipart').status_code == 404
        assert upload(app, file=SimpleUploadedFile('virus.exe', b'MZ', content_type='application/octet-stream')).status_code == 400
        assert api().get(f'{BASE}/public/documents/', creds(app)).status_code == 200

    def test_reminders_go_to_families_with_missing_documents_once_a_week(self, world):
        complete = mk(world['a'], 'Complete')
        missing = mk(world['a'], 'Missing')
        closed = mk(world['a'], 'Closed', status='rejected')
        for name in ('Birth certificate', 'Recent report card', 'Passport-size photo'):
            upload(complete, name)
        admin = api(world['admin'])
        for item in admin.get(f'{BASE}/applications/{complete.pk}/checklist/').json()['items']:
            admin.post(f'{BASE}/applications/{complete.pk}/documents/{item["document"]["id"]}/review/', {'status': 'received'}, format='json')
        mail.outbox.clear()
        call_command('admissions_daily')
        recipients = [m.to[0] for m in mail.outbox if 'Documents still needed' in m.subject]
        assert recipients == [missing.applicant.email] and closed.applicant.email not in recipients
        mail.outbox.clear()
        call_command('admissions_daily')
        assert not [m for m in mail.outbox if 'Documents still needed' in m.subject]        # not again within a week
        Application.objects.filter(pk=missing.pk).update(docs_reminded_at=timezone.now() - timedelta(days=8))
        call_command('admissions_daily')
        assert len([m for m in mail.outbox if 'Documents still needed' in m.subject]) == 1

    def test_documents_move_onto_the_student_when_enrolled(self, world):
        admin = api(world['admin'])
        app = mk(world['a'], 'Family')
        upload(app, 'Birth certificate'); upload(app, 'Recent report card')
        items = admin.get(f'{BASE}/applications/{app.pk}/checklist/').json()['items']
        report = next(i for i in items if i['name'] == 'Recent report card')
        admin.post(f'{BASE}/applications/{app.pk}/documents/{report["document"]["id"]}/review/', {'status': 'redo', 'note': 'Wrong year'}, format='json')
        assert set_status(admin, app, 'approved').status_code == 200
        res = admin.post(f'{BASE}/applications/{app.pk}/enroll/', {}, format='json')
        assert res.status_code == 200, res.content
        docs = StudentDocument.all_objects.filter(student__pk=res.json()['student_uuid'])
        assert [(d.title, d.category, d.from_family) for d in docs] == [('Birth certificate', 'identity', True)]  # the redo one stays behind
        assert docs[0].file.read() == b'%PDF-1.4 test'

    def test_other_schools_cannot_review(self, world):
        app = mk(world['a'], 'Family')
        upload(app)
        doc_id = api(world['admin']).get(f'{BASE}/applications/{app.pk}/checklist/').json()['items'][0]['document']['id']
        other = api(world['admin_b'])
        assert other.get(f'{BASE}/applications/{app.pk}/checklist/').status_code == 404
        assert other.post(f'{BASE}/applications/{app.pk}/documents/{doc_id}/review/', {'status': 'received'}, format='json').status_code == 404


def ApplicationDocumentCount(app):
    from services.education.admissions.models import ApplicationDocument
    return ApplicationDocument.objects.filter(application=app).count()


class TestApplicationFee:
    FORM = {
        'first_name': 'Maya', 'last_name': 'Brooks', 'date_of_birth': '2017-03-14', 'gender': 'female', 'applying_for_class': 'Grade 5',
        'guardians': [{'first_name': 'Erin', 'last_name': 'Brooks', 'relationship': 'mother', 'email': 'erin@example.com', 'mobile_phone': '512-555-0100'}],
        'signature_name': 'Erin Brooks', 'agree_declaration': True, 'agree_privacy': True,
    }

    def _open(self, world, **extra):
        admin = api(world['admin'])
        assert admin.put(f'{BASE}/settings/', {'online_open': True, 'academic_year': YEAR, **extra}, format='json').status_code == 200
        return admin

    def _apply(self, world):
        r = api().post(f'{BASE}/public/{world["a"].subdomain}/apply/', {'data': json.dumps(self.FORM)}, format='multipart')
        assert r.status_code == 201, r.content
        return r.json()

    def test_settings_validate_the_fee(self, world):
        admin = api(world['admin'])
        assert admin.put(f'{BASE}/settings/', {'application_fee_amount': 'lots'}, format='json').status_code == 400
        assert admin.put(f'{BASE}/settings/', {'application_fee_amount': '-5'}, format='json').status_code == 400
        assert admin.put(f'{BASE}/settings/', {'application_fee_currency': 'DOLLARS'}, format='json').status_code == 400
        ok = admin.put(f'{BASE}/settings/', {'application_fee_amount': '25', 'application_fee_currency': 'usd'}, format='json').json()
        assert ok['application_fee_amount'] == '25' and ok['application_fee_currency'] == 'USD'

    def test_an_online_application_gets_the_fee_and_is_held_until_paid(self, world):
        admin = self._open(world, application_fee_amount='25.00')
        applied = self._apply(world)
        assert applied['fee'] == {'amount': '25.00', 'currency': 'USD'}
        app = Application.objects.get(application_no=applied['application_no'])
        assert api().get(f'{BASE}/public/fee/', creds(app)).json()['fee']['status'] == 'unpaid'
        assert set_status(admin, app, 'reviewing').status_code == 400
        assert admin.post(f'{BASE}/applications/{app.pk}/fee/mark-paid/', {'reference': 'Check 1042'}, format='json').status_code == 200
        assert admin.post(f'{BASE}/applications/{app.pk}/fee/mark-paid/').status_code == 400   # not twice
        assert set_status(admin, app, 'reviewing').status_code == 200

    def test_no_fee_when_the_school_does_not_charge_one(self, world):
        self._open(world)
        applied = self._apply(world)
        assert applied['fee'] is None and not ApplicationFee.objects.exists()
        assert set_status(api(world['admin']), Application.objects.get(application_no=applied['application_no']), 'reviewing').status_code == 200

    def test_waiving_needs_a_reason_and_releases_the_hold(self, world):
        admin = self._open(world, application_fee_amount='25')
        app = Application.objects.get(application_no=self._apply(world)['application_no'])
        assert admin.post(f'{BASE}/applications/{app.pk}/fee/waive/', {}, format='json').status_code == 400
        assert admin.post(f'{BASE}/applications/{app.pk}/fee/waive/', {'note': 'Staff child'}, format='json').status_code == 200
        assert set_status(admin, app, 'reviewing').status_code == 200
        assert admin.post(f'{BASE}/applications/{app.pk}/fee/waive/', {'note': 'again'}, format='json').status_code == 400

    def _fee(self, world, amount='25.00'):
        app = mk(world['a'], 'Maya')
        with use_tenant(world['a']):
            fee = ApplicationFee.objects.create(application=app, amount=amount, currency='USD')
        return app, fee

    def test_checkout_opens_a_card_page_or_says_payments_are_not_set_up(self, world, monkeypatch):
        app, fee = self._fee(world)
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        body = {**creds(app), 'success_url': 'https://school.test/paid', 'cancel_url': 'https://school.test/cancel'}
        assert api().post(f'{BASE}/public/fee/checkout/', body, format='json').status_code == 400
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_123')
        response = mock.Mock(status_code=200, content=b'{}')
        response.json.return_value = {'id': 'cs_1', 'url': 'https://checkout.stripe.test/cs_1'}
        with mock.patch.object(fees.requests, 'post', return_value=response) as post:
            r = api().post(f'{BASE}/public/fee/checkout/', body, format='json')
        assert r.status_code == 200 and r.json()['url'].endswith('cs_1')
        sent = post.call_args.kwargs['data']
        assert sent['line_items[0][price_data][unit_amount]'] == 2500 and sent['metadata[application_fee_id]'] == str(fee.pk)
        assert api().post(f'{BASE}/public/fee/checkout/', {**creds(app), 'success_url': 'javascript:alert(1)', 'cancel_url': 'x'}, format='json').status_code == 400

    def _event(self, fee, amount_total=2500, currency='usd', paid='paid'):
        return json.dumps({'type': 'checkout.session.completed', 'data': {'object': {
            'id': 'cs_1', 'payment_status': paid, 'amount_total': amount_total, 'currency': currency, 'payment_intent': 'pi_1',
            'metadata': {'application_fee_id': str(fee.pk)}}}}).encode()

    def _payments_switched_on(self, monkeypatch):
        # the webhook URL is behind the school's "online_payments" feature switch
        monkeypatch.setattr('services.core.features.middleware.resolve_all_features', lambda tenant=None, user=None: {'online_payments': True})

    def test_only_a_signed_matching_stripe_event_marks_the_fee_paid(self, world, monkeypatch):
        self._payments_switched_on(monkeypatch)
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_123')
        monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
        app, fee = self._fee(world)
        url = '/api/v1/auth/finance/payments/webhook/stripe/'

        def post(raw, signature):
            return api().post(url, raw, content_type='application/json', HTTP_STRIPE_SIGNATURE=signature)

        good = self._event(fee)
        r = post(good, 't=1,v1=bad')
        assert r.status_code == 400, (r.status_code, r.content)                                  # forged
        assert post(self._event(fee, amount_total=100), stripe_gateway.sign(self._event(fee, amount_total=100), 'whsec_test')).status_code == 400
        assert post(self._event(fee, paid='unpaid'), stripe_gateway.sign(self._event(fee, paid='unpaid'), 'whsec_test')).status_code == 200
        fee.refresh_from_db()
        assert fee.status == 'unpaid'
        assert post(good, stripe_gateway.sign(good, 'whsec_test')).status_code == 200
        fee.refresh_from_db()
        assert fee.status == 'paid' and fee.payment_reference == 'pi_1' and fee.paid_at
        events = app.events.count()
        assert post(good, stripe_gateway.sign(good, 'whsec_test')).status_code == 200        # replay changes nothing
        assert app.events.count() == events

    def test_other_events_are_still_ignored(self, world, monkeypatch):
        self._payments_switched_on(monkeypatch)
        raw = json.dumps({'type': 'checkout.session.completed', 'data': {'object': {'metadata': {'application_fee_id': 'not-a-uuid'}}}}).encode()
        r = api().post('/api/v1/auth/finance/payments/webhook/stripe/', raw, content_type='application/json', HTTP_STRIPE_SIGNATURE='t=1,v1=x')
        assert r.status_code == 200 and 'Ignored' in r.json()['message']
