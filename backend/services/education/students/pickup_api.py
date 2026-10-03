"""Front desk: who may collect each student, the release log, and the visitor sign-in book.

Everything here is for administrators and the front desk role only (see access.py). School isolation comes from the
tenant registry, so a query never returns another school's rows.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .access import FrontDeskOnly, audit_read, audit_write, is_front_desk
from .models import AuthorizedAdult, PickupRelease, Student, StudentGuardian, VisitorLog


class AuthorizedAdultSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorizedAdult
        exclude = ('tenant',)
        read_only_fields = ('created_at',)


class PickupReleaseSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    released_by_name = serializers.CharField(source='released_by.full_name', read_only=True, default='')

    class Meta:
        model = PickupRelease
        exclude = ('tenant',)
        read_only_fields = ('released_to_name', 'released_at', 'released_by', 'override_used')

    def validate(self, attrs):
        adult, guardian, student = attrs.get('authorized_adult'), attrs.get('guardian'), attrs['student']
        if bool(adult) == bool(guardian):
            raise serializers.ValidationError('Choose exactly one person: a guardian or an authorised adult.')
        if not attrs.get('id_confirmed'):
            raise serializers.ValidationError({'id_confirmed': 'Confirm that you checked their photo ID.'})

        override_reason = (attrs.get('override_reason') or '').strip()
        request = self.context['request']
        if adult:
            if adult.student_id != student.id:
                raise serializers.ValidationError({'authorized_adult': 'This person is not on this student\'s pickup list.'})
            if not adult.is_active:
                raise serializers.ValidationError({'authorized_adult': 'This person is no longer on the pickup list.'})
            if adult.do_not_release:
                # A hard stop. Only an administrator can override it, and only with a typed reason.
                from .access import role_of
                if role_of(request.user) != 'admin':
                    raise serializers.ValidationError({'authorized_adult': 'DO NOT RELEASE. Ask an administrator.'})
                if not override_reason:
                    raise serializers.ValidationError({'override_reason': 'DO NOT RELEASE. An administrator must type a reason to override.'})
                attrs['override_used'] = True
            attrs['released_to_name'] = adult.name
        else:
            link = StudentGuardian.objects.filter(student=student, guardian=guardian).first()
            if link is None:
                raise serializers.ValidationError({'guardian': 'This person is not a guardian of this student.'})
            if not link.can_pickup:
                raise serializers.ValidationError({'guardian': 'This guardian is not allowed to collect this student.'})
            attrs['released_to_name'] = guardian.full_name
        return attrs


class VisitorLogSerializer(serializers.ModelSerializer):
    on_site = serializers.BooleanField(read_only=True)

    class Meta:
        model = VisitorLog
        exclude = ('tenant',)
        read_only_fields = ('checked_out_at', 'checked_in_by', 'checked_out_by')


class AuthorizedAdultViewSet(viewsets.ModelViewSet):
    permission_classes = [FrontDeskOnly]
    serializer_class = AuthorizedAdultSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['student', 'do_not_release', 'is_active']
    search_fields = ['name', 'phone']

    def get_queryset(self):
        return AuthorizedAdult.objects.select_related('student')

    def list(self, request, *args, **kwargs):
        if request.query_params.get('student'):
            audit_read(request, 'pickup/authorized_adults', student_id=request.query_params['student'])
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        obj = serializer.save()
        audit_write(self.request, 'CREATE', 'pickup/authorized_adult', obj.pk, {'student': str(obj.student_id), 'do_not_release': obj.do_not_release})

    def perform_update(self, serializer):
        before = serializer.instance.do_not_release
        obj = serializer.save()
        audit_write(self.request, 'SECURITY' if before != obj.do_not_release else 'UPDATE', 'pickup/authorized_adult', obj.pk,
                    {'student': str(obj.student_id), 'do_not_release': obj.do_not_release})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        audit_write(request, 'DELETE', 'pickup/authorized_adult', obj.pk, {'student': str(obj.student_id)})
        if obj.releases.exists():  # the release log must keep pointing at someone, so take them off the list instead
            obj.is_active = False
            obj.save(update_fields=['is_active'])
        else:
            obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PickupReleaseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The release log. Entries can be added and read, never changed or removed."""
    permission_classes = [FrontDeskOnly]
    serializer_class = PickupReleaseSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['student', 'authorized_adult', 'guardian', 'early_dismissal']

    def get_queryset(self):
        return PickupRelease.objects.select_related('student', 'released_by')

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(released_by=self.request.user)
        audit_write(self.request, 'SECURITY' if obj.override_used else 'CREATE', 'pickup/release', obj.pk,
                    {'student': str(obj.student_id), 'to': obj.released_to_name, 'override': obj.override_used,
                     'override_reason': obj.override_reason if obj.override_used else ''})


class VisitorLogViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [FrontDeskOnly]
    serializer_class = VisitorLogSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'visiting', 'purpose', 'badge_number']

    def get_queryset(self):
        qs = VisitorLog.objects.all()
        params = self.request.query_params
        if params.get('on_site') in ('1', 'true', 'True'):
            qs = qs.filter(checked_out_at__isnull=True)
        if params.get('date_from'):
            qs = qs.filter(checked_in_at__date__gte=params['date_from'])
        if params.get('date_to'):
            qs = qs.filter(checked_in_at__date__lte=params['date_to'])
        return qs

    def perform_create(self, serializer):
        serializer.save(checked_in_by=self.request.user)

    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        visitor = self.get_object()
        if visitor.checked_out_at:
            return Response({'error': 'This visitor is already signed out.'}, status=status.HTTP_400_BAD_REQUEST)
        visitor.checked_out_at = timezone.now()
        visitor.checked_out_by = request.user
        visitor.save(update_fields=['checked_out_at', 'checked_out_by'])
        return Response(self.get_serializer(visitor).data)


@api_view(['GET'])
@permission_classes([FrontDeskOnly])
def pickup_list(request):
    """Everyone who may collect one student: guardians who can pick up, extra authorised adults, and anyone barred."""
    try:
        student = get_object_or_404(Student, pk=request.query_params.get('student'))
    except (ValueError, TypeError, DjangoValidationError):
        return Response({'error': 'Give a student.'}, status=status.HTTP_400_BAD_REQUEST)
    audit_read(request, 'pickup/pickup_list', student_id=student.pk)
    guardians = [{
        'kind': 'guardian', 'id': str(link.guardian_id), 'name': link.guardian.full_name,
        'relationship': link.guardian.get_relationship_display(), 'phone': link.guardian.mobile_phone,
        'can_pickup': link.can_pickup, 'custody_notes': link.custody_notes,
    } for link in StudentGuardian.objects.filter(student=student).select_related('guardian')]
    adults = [{
        'kind': 'adult', 'id': str(a.pk), 'name': a.name, 'relationship': a.relationship, 'phone': a.phone,
        'photo_path': a.photo_path, 'id_type': a.id_type, 'id_checked': a.id_checked,
        'do_not_release': a.do_not_release, 'court_order_note': a.court_order_note,
    } for a in student.authorized_adults.filter(is_active=True)]
    return Response({
        'student': {'id': str(student.pk), 'name': student.full_name, 'student_id': student.student_id},
        'guardians': guardians, 'authorized_adults': adults,
    })
