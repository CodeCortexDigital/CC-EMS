from rest_framework import serializers
from .models import FormTemplate, FormAssignment, FormResponse


class FormTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    assignments_count = serializers.SerializerMethodField()

    class Meta:
        model = FormTemplate
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'version']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_assignments_count(self, obj):
        return obj.assignments.count()


class FormAssignmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    form_title = serializers.SerializerMethodField()
    guardian_signed_name = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = FormAssignment
        fields = '__all__'
        read_only_fields = ['assigned_at', 'version_at_assign']

    def get_student_name(self, obj):
        return obj.student.full_name

    def get_form_title(self, obj):
        return obj.form_template.title

    def get_guardian_signed_name(self, obj):
        response = obj.responses.first()
        if response:
            return response.guardian.get_full_name() or response.guardian.username
        return None

    def get_is_overdue(self, obj):
        if obj.status in ['pending', 'overdue']:
            from django.utils import timezone
            return obj.due_date < timezone.now()
        return False


class FormResponseSerializer(serializers.ModelSerializer):
    guardian_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    form_title = serializers.SerializerMethodField()

    class Meta:
        model = FormResponse
        fields = '__all__'
        read_only_fields = ['signed_at', 'version_at_sign', 'cannot_be_edited']

    def get_guardian_name(self, obj):
        return obj.guardian.get_full_name() or obj.guardian.username

    def get_student_name(self, obj):
        return obj.assignment.student.full_name

    def get_form_title(self, obj):
        return obj.assignment.form_template.title