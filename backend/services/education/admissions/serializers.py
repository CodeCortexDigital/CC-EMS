from rest_framework import serializers
from .models import Applicant, Application

class ApplicantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Applicant
        fields = '__all__'


class ApplicationSerializer(serializers.ModelSerializer):
    applicant = ApplicantSerializer(read_only=True)
    applicant_id = serializers.UUIDField(write_only=True, required=False)
    fee = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ('application_no', 'submitted_at', 'docs_reminded_at')

    def get_fee(self, obj):
        fee = getattr(obj, 'fee', None) if hasattr(obj, 'fee') else None
        return {'amount': str(fee.amount), 'currency': fee.currency, 'status': fee.status, 'note': fee.note} if fee else None
    
    def create(self, validated_data):
        applicant_id = validated_data.pop('applicant_id', None)
        if applicant_id:
            from .models import Applicant
            applicant = Applicant.objects.get(id=applicant_id)
            validated_data['applicant'] = applicant
        return super().create(validated_data)
