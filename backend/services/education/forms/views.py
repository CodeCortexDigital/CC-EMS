"""Permission slips and e-signature forms.

Administrators build and publish forms and run the tracker. Parents see the forms for their own children and sign them
once. A signature stores who, when, the typed name, the answers and the exact text agreed to, and is never changed.
"""
import csv

from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from services.core.accounts.decorators import filter_students_for_user, get_user_role
from services.education.students.access import audit_write, parent_student_ids
from services.education.students.health_api import notify_parents
from services.education.students.models import Student

from .models import FormAssignment, FormResponse, FormTemplate

QUESTION_TYPES = ('yes_no', 'text', 'choice')


def is_form_admin(user) -> bool:
    return get_user_role(user) in ('admin', 'manager')


class AdminOrReadOnlyStaff(BasePermission):
    """Administrators manage forms; teachers may read the tracker; parents use the /my/ and sign endpoints."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        role = get_user_role(user)
        if role in ('admin', 'manager'):
            return True
        # Any other staff member (teacher, office) can read; what a tracker shows them is limited to their own students.
        return request.method in ('GET', 'HEAD', 'OPTIONS') and role not in (None, 'parent', 'student')


class ParentOnly(BasePermission):
    message = 'Only parents sign forms.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and get_user_role(request.user) == 'parent')


def clean_questions(questions):
    """Check the question list a form is built from and give every question a stable id."""
    if not isinstance(questions, list):
        raise serializers.ValidationError('Questions must be a list.')
    seen = set()
    out = []
    for i, q in enumerate(questions, 1):
        if not isinstance(q, dict) or not str(q.get('label', '')).strip():
            raise serializers.ValidationError(f'Question {i} needs a label.')
        kind = q.get('type', 'yes_no')
        if kind not in QUESTION_TYPES:
            raise serializers.ValidationError(f'Question {i}: type must be one of {", ".join(QUESTION_TYPES)}.')
        options = [str(o).strip() for o in (q.get('options') or []) if str(o).strip()]
        if kind == 'choice' and len(options) < 2:
            raise serializers.ValidationError(f'Question {i}: a choice question needs at least two options.')
        qid = str(q.get('id') or f'q{i}')
        if qid in seen:
            raise serializers.ValidationError(f'Question {i}: the id "{qid}" is used twice.')
        seen.add(qid)
        out.append({'id': qid, 'label': str(q['label']).strip(), 'type': kind, 'options': options if kind == 'choice' else [],
                    'required': bool(q.get('required', True))})
    return out


class FormTemplateSerializer(serializers.ModelSerializer):
    counts = serializers.SerializerMethodField()

    class Meta:
        model = FormTemplate
        exclude = ('tenant',)
        read_only_fields = ('status', 'version', 'previous', 'published_at', 'created_by', 'created_at')

    def get_counts(self, obj):
        rows = list(obj.assignments.values_list('status', flat=True))
        return {'total': len(rows), 'signed': rows.count('signed'), 'declined': rows.count('declined'), 'pending': rows.count('pending')}

    def validate_questions(self, value):
        return clean_questions(value)

    def validate(self, attrs):
        audience = attrs.get('audience', getattr(self.instance, 'audience', 'everyone'))
        classes = attrs.get('classes')
        if audience == 'classes' and classes is not None and not classes:
            raise serializers.ValidationError({'classes': 'Choose at least one class, or send it to everyone.'})
        return attrs


class FormAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    class_name = serializers.SerializerMethodField()
    title = serializers.CharField(source='template.title', read_only=True)
    due_date = serializers.DateField(source='template.due_date', read_only=True)
    signed_at = serializers.SerializerMethodField()
    signer_name = serializers.SerializerMethodField()

    class Meta:
        model = FormAssignment
        fields = ('id', 'template', 'title', 'student', 'student_name', 'class_name', 'status', 'due_date', 'last_reminded_at', 'signed_at', 'signer_name')

    def _response(self, obj):
        return getattr(obj, 'response', None) if hasattr(obj, 'response') else None

    def get_class_name(self, obj):
        return getattr(obj.student.current_class, 'name', '') if obj.student.current_class_id else ''

    def get_signed_at(self, obj):
        r = self._response(obj)
        return r.signed_at if r else None

    def get_signer_name(self, obj):
        r = self._response(obj)
        return r.signer_name if r else ''


class FormTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [AdminOrReadOnlyStaff]
    serializer_class = FormTemplateSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']  # forms are archived, not deleted

    def get_queryset(self):
        return FormTemplate.objects.prefetch_related('assignments')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        template = serializer.instance
        wording = {'body', 'questions', 'title'} & set(serializer.validated_data)
        if template.status == 'archived':
            raise serializers.ValidationError('This form is archived.')
        if template.status == 'published' and wording and FormResponse.objects.filter(assignment__template=template).exists():
            raise serializers.ValidationError('Families have already signed this form, so its wording cannot change. Use "new version" instead.')
        serializer.save()

    @staticmethod
    def _audience_students(template):
        students = Student.objects.filter(is_active=True)
        if template.audience == 'classes':
            students = students.filter(current_class__in=template.classes.all())
        return students

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def publish(self, request, pk=None):
        template = self.get_object()
        if template.status != 'draft':
            return Response({'error': 'Only a draft can be published.'}, status=status.HTTP_400_BAD_REQUEST)
        if not template.body.strip():
            return Response({'error': 'Write the text families will agree to first.'}, status=status.HTTP_400_BAD_REQUEST)
        if template.audience == 'classes' and not template.classes.exists():
            return Response({'error': 'Choose which classes it goes to.'}, status=status.HTTP_400_BAD_REQUEST)
        students = list(self._audience_students(template))
        if not students:
            return Response({'error': 'No active students match this audience.'}, status=status.HTTP_400_BAD_REQUEST)
        FormAssignment.objects.bulk_create([FormAssignment(template=template, student=s) for s in students], ignore_conflicts=True)
        template.status, template.published_at = 'published', timezone.now()
        template.save(update_fields=['status', 'published_at'])
        told = sum(notify_parents(s, 'New form to sign', f'Please read and sign "{template.title}" for {s.full_name}.') for s in students)
        audit_write(request, 'CREATE', 'forms/publish', template.pk, {'students': len(students), 'parents_told': told})
        return Response(self.get_serializer(template).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def new_version(self, request, pk=None):
        """Copy a form that families have signed into a new draft (version + 1) and archive the old one."""
        old = self.get_object()
        if old.status != 'published':
            return Response({'error': 'Only a published form can get a new version.'}, status=status.HTTP_400_BAD_REQUEST)
        new = FormTemplate.objects.create(title=old.title, body=old.body, questions=old.questions, audience=old.audience,
                                          due_date=old.due_date, version=old.version + 1, previous=old, created_by=request.user)
        new.classes.set(old.classes.all())
        old.status = 'archived'
        old.save(update_fields=['status'])
        return Response(self.get_serializer(new).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        template = self.get_object()
        template.status = 'archived'
        template.save(update_fields=['status'])
        return Response(self.get_serializer(template).data)

    def _tracker_rows(self, template, request):
        qs = template.assignments.select_related('student', 'student__current_class', 'response')
        if is_form_admin(request.user):
            return qs
        return qs.filter(student__in=filter_students_for_user(request.user, Student.objects.all()))

    @action(detail=True, methods=['get'])
    def tracker(self, request, pk=None):
        template = self.get_object()
        rows = self._tracker_rows(template, request)
        want = request.query_params.get('status')
        statuses = list(rows.values_list('status', flat=True))
        if want:
            rows = rows.filter(status=want)
        return Response({
            'template': template.title, 'due_date': template.due_date,
            'counts': {'total': len(statuses), 'signed': statuses.count('signed'), 'declined': statuses.count('declined'), 'pending': statuses.count('pending')},
            'rows': FormAssignmentSerializer(rows, many=True).data,
        })

    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        template = self.get_object()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="form-{template.pk}.csv"'
        out = csv.writer(response)
        questions = template.questions
        out.writerow(['Student', 'Class', 'Status', 'Signed by', 'Signed at'] + [q['label'] for q in questions])
        for a in self._tracker_rows(template, request):
            r = getattr(a, 'response', None) if hasattr(a, 'response') else None
            out.writerow([a.student.full_name, getattr(a.student.current_class, 'name', ''), a.get_status_display(),
                          r.signer_name if r else '', r.signed_at.isoformat() if r else ''] + [(r.answers.get(q['id'], '') if r else '') for q in questions])
        return response

    @action(detail=True, methods=['post'])
    def remind(self, request, pk=None):
        """Remind the families who have not signed yet. Never reminds anyone who has signed or declined."""
        if not is_form_admin(request.user):
            return Response({'detail': 'Only administrators can send reminders.'}, status=status.HTTP_403_FORBIDDEN)
        template = self.get_object()
        if template.status != 'published':
            return Response({'error': 'Only a published form can be reminded.'}, status=status.HTTP_400_BAD_REQUEST)
        pending = list(template.assignments.filter(status='pending').select_related('student'))
        told = 0
        for a in pending:
            told += notify_parents(a.student, 'Reminder: form to sign', f'Please sign "{template.title}" for {a.student.full_name}.')
            a.last_reminded_at = timezone.now()
        FormAssignment.objects.bulk_update(pending, ['last_reminded_at'])
        return Response({'reminded': len(pending), 'parents_told': told})


class MyFormsViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """A parent's own forms, one per child, and the sign action."""
    permission_classes = [ParentOnly]
    serializer_class = FormAssignmentSerializer

    def get_queryset(self):
        return (FormAssignment.objects.filter(student_id__in=parent_student_ids(self.request.user), template__status__in=('published', 'archived'))
                .select_related('student', 'student__current_class', 'template'))

    def retrieve(self, request, *args, **kwargs):
        a = self.get_object()
        data = FormAssignmentSerializer(a).data
        data['body'], data['questions'] = a.template.body, a.template.questions
        if hasattr(a, 'response'):
            data['answers'] = a.response.answers
        return Response(data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def sign(self, request, pk=None):
        a = self.get_object()
        template = a.template
        if template.status != 'published':
            return Response({'error': 'This form is no longer open for signing.'}, status=status.HTTP_400_BAD_REQUEST)
        if a.status != 'pending' or FormResponse.objects.filter(assignment=a).exists():
            return Response({'error': 'This form has already been answered. A signature cannot be changed.'}, status=status.HTTP_400_BAD_REQUEST)

        decision = request.data.get('decision', 'signed')
        if decision not in ('signed', 'declined'):
            return Response({'decision': 'Choose to sign or decline.'}, status=status.HTTP_400_BAD_REQUEST)
        name = str(request.data.get('signer_name') or '').strip()
        if not name:
            return Response({'signer_name': 'Type your full name to sign.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get('agree') is not True:
            return Response({'agree': 'Tick the box to confirm you agree.'}, status=status.HTTP_400_BAD_REQUEST)

        answers = request.data.get('answers') or {}
        if not isinstance(answers, dict):
            return Response({'answers': 'Answers must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
        clean = {}
        for q in template.questions:
            value = answers.get(q['id'])
            blank = value is None or (isinstance(value, str) and not value.strip())
            if decision == 'signed' and q.get('required', True) and blank:
                return Response({q['id']: f'Please answer: {q["label"]}'}, status=status.HTTP_400_BAD_REQUEST)
            if blank:
                continue
            if q['type'] == 'yes_no' and value not in ('yes', 'no', True, False):
                return Response({q['id']: 'Answer yes or no.'}, status=status.HTTP_400_BAD_REQUEST)
            if q['type'] == 'choice' and value not in q['options']:
                return Response({q['id']: 'Choose one of the options.'}, status=status.HTTP_400_BAD_REQUEST)
            clean[q['id']] = value

        try:
            FormResponse.objects.create(
                assignment=a, signer=request.user, signer_name=name, decision=decision, answers=clean, text_snapshot=template.snapshot(),
                ip_address=request.META.get('REMOTE_ADDR') or None, user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512])
        except IntegrityError:
            return Response({'error': 'This form has already been answered.'}, status=status.HTTP_400_BAD_REQUEST)
        a.status = decision
        a.save(update_fields=['status'])
        audit_write(request, 'CREATE', 'forms/signature', a.pk, {'student': str(a.student_id), 'decision': decision})
        return Response(self.get_serializer(a).data, status=status.HTTP_201_CREATED)
