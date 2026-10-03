"""Admissions extras: the waiting list and seat offers, school tours and interviews, the document checklist, and
the application fee.

Administrators manage everything here. Families use the public (no login) endpoints with their application number and
tracking code, the same way they check the status of an application.
"""
from django.apps import apps
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, parser_classes, permission_classes, throttle_classes
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from services.core.tenants.context import use_tenant

from . import fee as fees
from . import waitlist
from .models import Application, ApplicationDocument, Offer, TourBooking, TourSlot, WaitlistConfig, WaitlistEntry
from .views import AdminOnly, _doc_payload, _email, _log, _settings

School = apps.get_model('core_tenants', 'School')
NOT_FOUND = 'No application matches that number and tracking code.'


class TokenThrottle(AnonRateThrottle):
    scope = 'admission_token'
    rate = '240/hour'


def token_application(data):
    """The application a family means, from its number and tracking code (and its school)."""
    number, token = str(data.get('no') or '').strip(), str(data.get('token') or '').strip()
    if not number or not token:
        return None, None
    with use_tenant(None):
        app = Application.objects.select_related('applicant').filter(application_no__iexact=number, tracking_token=token).first()
        school = School.objects.filter(pk=app.applicant.tenant_id).first() if app else None
    return (app, school) if app and school else (None, None)


def public(*methods):
    """A family-facing endpoint: no login, throttled, any of JSON, form or file uploads."""
    def wrap(fn):
        fn = parser_classes([JSONParser, FormParser, MultiPartParser])(fn)
        fn = throttle_classes([TokenThrottle])(fn)
        fn = permission_classes([AllowAny])(fn)
        fn = authentication_classes([])(fn)
        return api_view(list(methods))(fn)
    return wrap


def clean_uuid(value):
    """The value as a UUID string, or None if it is not one (so a bad id from outside never crashes a query)."""
    import uuid
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None


def _params(request):
    return request.query_params if request.method == 'GET' else request.data


# ---------------------------------------------------------------------------------------------------- waiting list

class WaitlistConfigSerializer(serializers.ModelSerializer):
    seats_taken = serializers.SerializerMethodField()
    open_offers = serializers.SerializerMethodField()
    seats_left = serializers.SerializerMethodField()
    waiting = serializers.SerializerMethodField()

    class Meta:
        model = WaitlistConfig
        exclude = ('tenant',)

    def get_seats_taken(self, o):
        return waitlist.seats_taken(o)

    def get_open_offers(self, o):
        return waitlist.open_offer_count(o)

    def get_seats_left(self, o):
        return waitlist.seats_left(o)

    def get_waiting(self, o):
        return len(waitlist.ranked_entries(o))

    def validate(self, attrs):
        grade = attrs.get('class_name', getattr(self.instance, 'class_name', ''))
        year = attrs.get('academic_year', getattr(self.instance, 'academic_year', ''))
        clash = WaitlistConfig.objects.filter(class_name__iexact=grade, academic_year=year)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(f'{grade} for {year} already has its seats set. Change that one instead.')
        return attrs


class WaitlistEntrySerializer(serializers.ModelSerializer):
    application_no = serializers.CharField(source='application.application_no', read_only=True)
    student_name = serializers.CharField(source='application.applicant.full_name', read_only=True)
    grade = serializers.CharField(source='application.applicant.applying_for_class', read_only=True)
    sibling = serializers.SerializerMethodField()

    class Meta:
        model = WaitlistEntry
        fields = ('id', 'application', 'application_no', 'student_name', 'grade', 'sibling', 'staff_child', 'joined_at', 'status')
        read_only_fields = ('application', 'joined_at', 'status')

    def get_sibling(self, o):
        return bool(o.application.applicant.sibling_at_school.strip())


class OfferSerializer(serializers.ModelSerializer):
    application_no = serializers.CharField(source='entry.application.application_no', read_only=True)
    student_name = serializers.CharField(source='entry.application.applicant.full_name', read_only=True)

    class Meta:
        model = Offer
        fields = ('id', 'entry', 'application_no', 'student_name', 'offered_at', 'expires_at', 'status', 'responded_at')


class WaitlistConfigViewSet(viewsets.ModelViewSet):
    permission_classes = [AdminOnly]
    serializer_class = WaitlistConfigSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return WaitlistConfig.objects.all()

    def perform_create(self, serializer):
        config = serializer.save()
        waitlist.fill(config)

    def perform_update(self, serializer):
        config = serializer.save()
        waitlist.fill(config)  # more seats means offers go out now

    @action(detail=True, methods=['post'])
    def fill(self, request, pk=None):
        offers = waitlist.fill(self.get_object())
        return Response({'offers_made': len(offers)})

    @action(detail=True, methods=['get'])
    def entries(self, request, pk=None):
        config = self.get_object()
        ranked = waitlist.ranked_entries(config)
        data = WaitlistEntrySerializer(ranked, many=True).data
        for position, row in enumerate(data, 1):
            row['position'] = position
        return Response({'config': self.get_serializer(config).data, 'entries': data})

    @action(detail=True, methods=['post'])
    def add(self, request, pk=None):
        """Put an application on this grade's waiting list (it becomes 'waitlisted')."""
        config = self.get_object()
        app = Application.objects.select_related('applicant').filter(pk=clean_uuid(request.data.get('application'))).first()
        if app is None:
            return Response({'error': 'Choose an application.'}, status=status.HTTP_400_BAD_REQUEST)
        if (app.applicant.applying_for_class.lower(), app.academic_year) != (config.class_name.lower(), config.academic_year):
            return Response({'error': 'That application is for a different grade or year.'}, status=status.HTTP_400_BAD_REQUEST)
        if app.status in ('enrolled', 'rejected', 'withdrawn'):
            return Response({'error': f'A {app.get_status_display().lower()} application cannot join the waiting list.'}, status=status.HTTP_400_BAD_REQUEST)
        if fees.is_held(app):
            return Response({'error': 'The application fee has not been paid yet.'}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            if app.status != 'waitlisted':
                _log(app, 'waitlisted', 'Added to the waiting list', request.user)
                app.status, app.decided_at = 'waitlisted', timezone.now()
                app.save(update_fields=['status', 'decided_at', 'updated_at'])
            entry = waitlist.ensure_entry(app)
            entry.staff_child = bool(request.data.get('staff_child', entry.staff_child))
            entry.save(update_fields=['staff_child'])
            waitlist.fill(config)
        return Response(WaitlistEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class WaitlistEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [AdminOnly]
    serializer_class = WaitlistEntrySerializer
    http_method_names = ['get', 'patch', 'post', 'head', 'options']
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_queryset(self):
        return WaitlistEntry.objects.select_related('application', 'application__applicant')

    @action(detail=True, methods=['post'])
    def remove(self, request, pk=None):
        entry = self.get_object()
        if entry.status == 'offered':
            return Response({'error': 'Withdraw the open offer first.'}, status=status.HTTP_400_BAD_REQUEST)
        entry.status = 'removed'
        entry.save(update_fields=['status'])
        return Response(self.get_serializer(entry).data)


class OfferViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [AdminOnly]
    serializer_class = OfferSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_queryset(self):
        return Offer.objects.select_related('entry__application__applicant')

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def withdraw(self, request, pk=None):
        offer = self.get_object()
        if offer.status != 'offered':
            return Response({'error': 'Only an open offer can be withdrawn.'}, status=status.HTTP_400_BAD_REQUEST)
        offer.status, offer.responded_at = 'withdrawn', timezone.now()
        offer.save(update_fields=['status', 'responded_at'])
        offer.entry.status = 'removed'
        offer.entry.save(update_fields=['status'])
        waitlist.release_seat(offer.entry.application)
        return Response(self.get_serializer(offer).data)


@public('GET', 'POST')
def public_offer(request):
    app, school = token_application(_params(request))
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    with use_tenant(school):
        offer = Offer.objects.filter(entry__application=app, status='offered').first()
        if request.method == 'GET':
            return Response({'application_no': app.application_no, 'student': app.applicant.full_name, 'grade': app.applicant.applying_for_class,
                             'status': app.status, 'offer': {'id': str(offer.pk), 'expires_at': offer.expires_at} if offer else None})
        decision = request.data.get('decision')
        if decision not in ('accept', 'decline'):
            return Response({'error': 'Choose accept or decline.'}, status=400)
        if offer is None:
            return Response({'error': 'There is no open offer for this application.'}, status=400)
        try:
            waitlist.respond(offer, decision == 'accept')
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        _email(_settings(school)['notify_email'], f'Seat {decision}ed: {app.application_no}', f'{app.applicant.full_name} ({app.applicant.applying_for_class}) {decision}ed the offered seat.')
        app.refresh_from_db()
        return Response({'status': app.status, 'decision': decision})


# ---------------------------------------------------------------------------------------------------- tours

class TourSlotSerializer(serializers.ModelSerializer):
    booked = serializers.SerializerMethodField()
    seats_left = serializers.SerializerMethodField()

    class Meta:
        model = TourSlot
        exclude = ('tenant',)

    def get_booked(self, o):
        return o.bookings.filter(status='booked').count()

    def get_seats_left(self, o):
        return max(0, o.capacity - self.get_booked(o))

    def validate(self, attrs):
        starts, ends = attrs.get('starts_at', getattr(self.instance, 'starts_at', None)), attrs.get('ends_at', getattr(self.instance, 'ends_at', None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError({'ends_at': 'The end must be after the start.'})
        if self.instance and attrs.get('capacity') is not None and attrs['capacity'] < self.get_booked(self.instance):
            raise serializers.ValidationError({'capacity': 'More families than that have already booked this time.'})
        return attrs


class TourBookingSerializer(serializers.ModelSerializer):
    application_no = serializers.CharField(source='application.application_no', read_only=True)
    student_name = serializers.CharField(source='application.applicant.full_name', read_only=True)
    starts_at = serializers.DateTimeField(source='slot.starts_at', read_only=True)
    kind = serializers.CharField(source='slot.kind', read_only=True)

    class Meta:
        model = TourBooking
        fields = ('id', 'slot', 'kind', 'starts_at', 'application', 'application_no', 'student_name', 'status', 'created_at')


class TourSlotViewSet(viewsets.ModelViewSet):
    permission_classes = [AdminOnly]
    serializer_class = TourSlotSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kind', 'is_open']

    def get_queryset(self):
        return TourSlot.objects.all()

    def destroy(self, request, *args, **kwargs):
        slot = self.get_object()
        if slot.bookings.filter(status='booked').exists():
            return Response({'error': 'Families have booked this time. Close it instead, after cancelling their bookings.'}, status=400)
        return super().destroy(request, *args, **kwargs)


class TourBookingViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [AdminOnly]
    serializer_class = TourBookingSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['slot', 'status', 'application']

    def get_queryset(self):
        return TourBooking.objects.select_related('slot', 'application', 'application__applicant')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status != 'booked':
            return Response({'error': 'Already cancelled.'}, status=400)
        _cancel_booking(booking, request.user)
        return Response(self.get_serializer(booking).data)


def _cancel_booking(booking, user=None):
    booking.status = 'cancelled'
    booking.save(update_fields=['status'])
    app = booking.application
    if booking.slot.kind == 'interview' and app.interview_date == booking.slot.starts_at:
        app.interview_date = None
        app.save(update_fields=['interview_date', 'updated_at'])
    _log(app, app.status, f'{booking.slot.get_kind_display()} booking cancelled', user)


@public('GET', 'POST')
def public_tours(request):
    """GET: times a family can book (and their own bookings). POST: book one."""
    app, school = token_application(_params(request))
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    with use_tenant(school):
        if request.method == 'GET':
            kind = request.query_params.get('kind') or 'tour'
            slots = [s for s in TourSlot.objects.filter(kind=kind, is_open=True, starts_at__gt=timezone.now()) if TourSlotSerializer().get_seats_left(s) > 0]
            mine = TourBooking.objects.filter(application=app, status='booked').select_related('slot')
            return Response({'slots': TourSlotSerializer(slots, many=True).data, 'my_bookings': TourBookingSerializer(mine, many=True).data})
        with transaction.atomic():
            slot = TourSlot.objects.select_for_update().filter(pk=clean_uuid(request.data.get('slot'))).first()
            if slot is None or not slot.is_open or slot.starts_at <= timezone.now():
                return Response({'error': 'That time is not available.'}, status=400)
            if TourBooking.objects.filter(application=app, status='booked', slot__kind=slot.kind, slot__starts_at__gt=timezone.now()).exists():
                return Response({'error': f'You already have a {slot.get_kind_display().lower()} booked. Cancel it first to choose another time.'}, status=400)
            if slot.bookings.filter(status='booked').count() >= slot.capacity:
                return Response({'error': 'That time is full. Please choose another.'}, status=400)
            booking = TourBooking.objects.create(slot=slot, application=app)
            if slot.kind == 'interview':
                app.interview_date = slot.starts_at
                app.save(update_fields=['interview_date', 'updated_at'])
            _log(app, app.status, f'Booked {slot.get_kind_display().lower()} for {timezone.localtime(slot.starts_at):%b %d, %I:%M %p}')
        _email(app.applicant.email, f'{slot.get_kind_display()} booked: {timezone.localtime(slot.starts_at):%b %d, %I:%M %p}',
               f'Your {slot.get_kind_display().lower()} is booked for {timezone.localtime(slot.starts_at):%A, %B %d at %I:%M %p}.\n{slot.location}\n\nChange or cancel it here: {waitlist.portal_link(app)}')
        return Response(TourBookingSerializer(booking).data, status=201)


@public('POST')
def public_tours_cancel(request):
    app, school = token_application(request.data)
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    with use_tenant(school):
        booking = TourBooking.objects.filter(pk=clean_uuid(request.data.get('booking')), application=app, status='booked').select_related('slot').first()
        if booking is None:
            return Response({'error': 'No such booking.'}, status=404)
        _cancel_booking(booking)
        return Response(TourBookingSerializer(booking).data)


# ---------------------------------------------------------------------------------------------------- documents

STATES = {'pending': 'uploaded', 'received': 'received', 'redo': 'redo'}


def checklist(application, school):
    """Every document the school asks for, and where each one stands for this application."""
    required = _settings(school)['required_documents']
    docs = list(application.documents.all())
    items = []
    for name in required:
        mine = [d for d in docs if d.doc_type.strip().lower() == name.strip().lower()]
        latest = max(mine, key=lambda d: d.uploaded_at) if mine else None
        items.append({'name': name, 'state': STATES[latest.review_status] if latest else 'missing',
                      'document': _doc_payload(latest) if latest else None, 'note': latest.review_note if latest else ''})
    return items


@api_view(['GET'])
@permission_classes([AdminOnly])
def application_checklist(request, id):
    application = get_object_or_404(Application.objects.select_related('applicant'), id=id)
    school = School.objects.get(pk=application.applicant.tenant_id)
    items = checklist(application, school)
    return Response({'items': items, 'complete': all(i['state'] == 'received' for i in items)})


@api_view(['POST'])
@permission_classes([AdminOnly])
def review_document(request, id, doc_id):
    doc = get_object_or_404(ApplicationDocument, id=doc_id, application_id=id)
    decision, note = request.data.get('status'), str(request.data.get('note') or '').strip()
    if decision not in ('received', 'redo'):
        return Response({'error': 'Choose received or needs sending again.'}, status=400)
    if decision == 'redo' and not note:
        return Response({'error': 'Tell the family what to send again.'}, status=400)
    doc.review_status, doc.review_note, doc.reviewed_at, doc.reviewed_by = decision, note, timezone.now(), request.user
    doc.save(update_fields=['review_status', 'review_note', 'reviewed_at', 'reviewed_by'])
    app = doc.application
    _log(app, app.status, f'{doc.doc_type}: {"received" if decision == "received" else "needs sending again - " + note}', request.user)
    if decision == 'redo':
        _email(app.applicant.email, f'Please send {doc.doc_type} again: {app.application_no}',
               f'The school could not use the {doc.doc_type} you sent.\n{note}\n\nPlease upload it again here: {waitlist.portal_link(app)}\n'
               f'(application number {app.application_no}, tracking code {app.tracking_token})')
    return Response(_doc_payload(doc) | {'review_status': doc.review_status, 'review_note': doc.review_note})


@public('GET', 'POST')
def public_documents(request):
    """GET: the checklist. POST (multipart: no, token, doc_type, file): send a document or send it again."""
    from services.core.storage.utils import validate_upload

    app, school = token_application(_params(request))
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    with use_tenant(school):
        if request.method == 'GET':
            return Response({'items': checklist(app, school)})
        if app.status in ('rejected', 'withdrawn', 'enrolled'):
            return Response({'error': 'This application is closed.'}, status=400)
        file = request.FILES.get('file')
        doc_type = str(request.data.get('doc_type') or '').strip()
        required = [r.lower() for r in _settings(school)['required_documents']]
        if file is None or not doc_type:
            return Response({'error': 'Choose the document and a file.'}, status=400)
        if doc_type.lower() not in required:
            return Response({'error': 'That is not one of the documents the school asked for.'}, status=400)
        existing = [d for d in app.documents.all() if d.doc_type.strip().lower() == doc_type.lower()]
        if any(d.review_status == 'received' for d in existing):
            return Response({'error': 'The school has already received this document.'}, status=400)
        try:
            info = validate_upload(file, file.name, declared_content_type=getattr(file, 'content_type', None))
        except DjangoValidationError as exc:
            return Response({'error': ' '.join(exc.messages)}, status=400)
        with transaction.atomic():
            for old in existing:  # a new file replaces the one that was sent before
                old.file.delete(save=False)
                old.delete()
            doc = ApplicationDocument.objects.create(application=app, doc_type=doc_type[:60], file=file, original_name=info.name, size=info.size)
            _log(app, app.status, f'Family sent {doc.doc_type}', by_name='Family')
        return Response({'items': checklist(app, school)}, status=201)


# ---------------------------------------------------------------------------------------------------- fee

@api_view(['POST'])
@permission_classes([AdminOnly])
def fee_waive(request, id):
    app = get_object_or_404(Application, id=id)
    fee = getattr(app, 'fee', None) if hasattr(app, 'fee') else None
    note = str(request.data.get('note') or '').strip()
    if fee is None:
        return Response({'error': 'This application has no fee.'}, status=400)
    if not note:
        return Response({'error': 'Say why the fee is waived.'}, status=400)
    try:
        fees.waive(fee, note, getattr(request.user, 'full_name', ''))
    except ValueError as exc:
        return Response({'error': str(exc)}, status=400)
    return Response({'status': 'waived'})


@api_view(['POST'])
@permission_classes([AdminOnly])
def fee_mark_paid(request, id):
    """Cash or cheque paid at the office."""
    app = get_object_or_404(Application, id=id)
    fee = getattr(app, 'fee', None) if hasattr(app, 'fee') else None
    if fee is None:
        return Response({'error': 'This application has no fee.'}, status=400)
    if fee.status != 'unpaid':
        return Response({'error': f'The fee is already {fee.get_status_display().lower()}.'}, status=400)
    fees.mark_paid(fee, reference=str(request.data.get('reference') or 'Paid at the office'), by=getattr(request.user, 'full_name', ''))
    return Response({'status': 'paid'})


def _fee_payload(fee):
    return {'amount': str(fee.amount), 'currency': fee.currency, 'status': fee.status} if fee else None


@public('GET')
def public_fee(request):
    app, school = token_application(request.query_params)
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    with use_tenant(school):
        return Response({'fee': _fee_payload(getattr(app, 'fee', None) if hasattr(app, 'fee') else None)})


@public('POST')
def public_fee_checkout(request):
    from services.education.finance.payments.gateways import get_active_gateway_config

    app, school = token_application(request.data)
    if app is None:
        return Response({'error': NOT_FOUND}, status=404)
    success, cancel = str(request.data.get('success_url') or ''), str(request.data.get('cancel_url') or '')
    if not (success.startswith(('http://', 'https://')) and cancel.startswith(('http://', 'https://'))):
        return Response({'error': 'Give the page to return to after paying.'}, status=400)
    with use_tenant(school):
        fee = getattr(app, 'fee', None) if hasattr(app, 'fee') else None
        if fee is None:
            return Response({'error': 'This application has no fee.'}, status=400)
        try:
            url = fees.start_checkout(fee, get_active_gateway_config('stripe', tenant=school), success, cancel, app.applicant.email)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        return Response({'url': url})
