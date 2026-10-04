from django.urls import path

from . import directory, payroll, records, substitutes
from services.education.insights.planning import staffing as staffing_signals

urlpatterns = [
    path('overview/', records.overview, name='hr-overview'),
    path('alerts/', records.alerts_view, name='hr-alerts'),
    path('signals/', staffing_signals, name='hr-signals'),
    path('me/', records.my_hr, name='hr-me'),
    # Cover requests
    path('cover/', substitutes.requests_, name='hr-cover'),
    path('cover/absence/', substitutes.absence, name='hr-cover-absence'),
    path('cover/periods/', substitutes.my_periods, name='hr-cover-periods'),
    path('cover/<str:request_id>/candidates/', substitutes.candidates, name='hr-cover-candidates'),
    path('cover/<str:request_id>/<str:action>/', substitutes.act, name='hr-cover-action'),
    # Recruitment and onboarding
    path('openings/', records.OpeningList.as_view(), name='hr-openings'),
    path('openings/<str:pk>/', records.OpeningDetail.as_view(), name='hr-opening'),
    path('candidates/', records.CandidateList.as_view(), name='hr-candidates'),
    path('candidates/<str:pk>/', records.CandidateDetail.as_view(), name='hr-candidate'),
    path('candidates/<str:candidate_id>/stage/', records.candidate_stage, name='hr-candidate-stage'),
    path('candidates/<str:candidate_id>/hire/', records.candidate_hire, name='hr-candidate-hire'),
    path('onboarding/', records.OnboardingList.as_view(), name='hr-onboarding'),
    path('onboarding/start/', records.onboarding_start, name='hr-onboarding-start'),
    path('onboarding/<str:pk>/', records.OnboardingDetail.as_view(), name='hr-onboarding-task'),
    # Contracts and credentials
    path('contracts/', records.ContractList.as_view(), name='hr-contracts'),
    path('contracts/<str:pk>/', records.ContractDetail.as_view(), name='hr-contract'),
    path('credentials/', records.CredentialList.as_view(), name='hr-credentials'),
    path('credentials/<str:pk>/', records.CredentialDetail.as_view(), name='hr-credential'),
    # Performance
    path('reviews/', records.ReviewList.as_view(), name='hr-reviews'),
    path('reviews/<str:pk>/', records.ReviewDetail.as_view(), name='hr-review'),
    path('reviews/<str:review_id>/acknowledge/', records.acknowledge_review, name='hr-review-ack'),
    path('goals/', records.GoalList.as_view(), name='hr-goals'),
    path('goals/<str:pk>/', records.GoalDetail.as_view(), name='hr-goal'),
    # Pay setup
    path('payroll/grades/', payroll.GradeList.as_view(), name='hr-pay-grades'),
    path('payroll/grades/<str:pk>/', payroll.GradeDetail.as_view(), name='hr-pay-grade'),
    path('payroll/profiles/', payroll.profiles, name='hr-pay-profiles'),
    path('payroll/profiles/<str:teacher_id>/', payroll.profile, name='hr-pay-profile'),
    # Directory and org chart
    path('directory/', directory.directory, name='hr-directory'),
    path('directory/<str:teacher_id>/manager/', directory.set_manager, name='hr-set-manager'),
    path('org-chart/', directory.org_chart, name='hr-org-chart'),
]
