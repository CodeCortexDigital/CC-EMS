from django.urls import path

from . import api, planning

urlpatterns = [
    path('overview/', api.overview, name='insights-overview'),
    path('enrolment/', api.enrolment, name='insights-enrolment'),
    path('attendance/', api.attendance, name='insights-attendance'),
    path('finance/', api.finance, name='insights-finance'),
    path('academics/', api.academics, name='insights-academics'),
    path('teachers/', api.teachers, name='insights-teachers'),
    path('forecast/', planning.forecast, name='insights-forecast'),
    path('trends/', planning.trends, name='insights-trends'),
    path('narrative/', planning.narrative, name='insights-narrative'),
]
