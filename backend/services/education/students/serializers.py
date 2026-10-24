from rest_framework import serializers
from .models import Student, Certificate


def generate_unique_student_id(base=None, tenant=None):
    """The next free student number for this school, for example ``GVS-STU0007``.

    Student numbers are login names, so they are unique across every school. Each school's own code is part of the number it
    creates and it numbers from 1 on its own (see ``core/tenants/identifiers.py``).
    """
    from services.core.tenants.identifiers import next_id, with_prefix

    if base:
        return with_prefix(base, tenant)
    return next_id(Student, 'student_id', 'STU', tenant)

class StudentNumberMixin:
    """How a student number is handled. Used by every student serializer (the v1 and v2 API ones too).

    The number the school typed gets the school's own code in front, so two schools can both start at 0001. A number that is
    already taken is refused with a clear message (it is never silently changed). Blank means "number it for me"."""

    def validate_student_id(self, value):
        from services.core.tenants.identifiers import tenant_of, with_prefix

        tenant = tenant_of(self)
        value = (value or '').strip()
        if not value:
            return generate_unique_student_id(tenant=tenant)
        if self.instance is not None and value == self.instance.student_id:
            return value                                         # an existing number is left exactly as it is
        value = with_prefix(value, tenant)
        qs = Student.all_objects.filter(student_id=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This student number is already in use. Please choose another.')
        return value

    def fill_student_id(self, data):
        """A new student sent without a number gets the school's next one."""
        from services.core.tenants.identifiers import tenant_of

        if self.instance is None and not data.get('student_id'):
            data['student_id'] = generate_unique_student_id(tenant=tenant_of(self))
        return data


class StudentSerializer(StudentNumberMixin, serializers.ModelSerializer):
    class_name = serializers.CharField(source='current_class.name', read_only=True)
    section_name = serializers.CharField(source='current_section.name', read_only=True)
    attendance_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Student
        fields = '__all__'
        extra_kwargs = {
            'date_of_birth': {'required': False, 'allow_null': True},
            'admission_date': {'required': False, 'allow_null': True},
            'student_id': {'required': False, 'allow_blank': True},   # blank = the school's next number
        }
        
    def get_attendance_rate(self, obj):
        from services.education.attendance.models import AttendanceRecord
        records = AttendanceRecord.objects.filter(student=obj).exclude(status='holiday')
        total = records.count()
        if total == 0:
            return 0
        present = records.filter(status__in=['present', 'late']).count()
        return round((present / total) * 100)
    
    def to_internal_value(self, data):
        # Handle empty date strings
        if data.get('date_of_birth') == '':
            data['date_of_birth'] = None
        if data.get('admission_date') == '':
            data['admission_date'] = None
        return super().to_internal_value(data)

    def validate(self, data):
        """Ensure the target class has an available seat before admitting a
        student. Capacity is defined by SchoolClass.max_students and counts
        active, non-deleted students already assigned to that class."""
        self.fill_student_id(data)
        target_class = data.get('current_class', getattr(self.instance, 'current_class', None))
        if target_class is not None:
            max_students = getattr(target_class, 'max_students', None) or 0
            if max_students > 0:
                qs = Student.objects.filter(current_class=target_class, is_active=True)
                if self.instance is not None:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.count() >= max_students:
                    raise serializers.ValidationError({
                        'current_class': (
                            f'Class "{target_class.name}" is full '
                            f'({max_students}/{max_students} seats taken). '
                            'No available seats.'
                        )
                    })
        return data

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._link_family(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        self._link_family(instance)
        return instance

    def _link_family(self, instance):
        """Auto-detect siblings by parent NIC and keep the family label /
        sibling count in sync. Best-effort: never block a save on failure."""
        try:
            from .family_utils import link_family
            if link_family(instance):
                instance.refresh_from_db(fields=['select_family', 'total_siblings'])
        except Exception:
            pass



class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = '__all__'
