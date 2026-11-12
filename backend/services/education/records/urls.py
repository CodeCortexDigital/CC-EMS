from django.urls import path

from . import termreport_views as tr
from . import views

urlpatterns = [
    path('roster/', views.roster),
    path('open/', views.open_record),
    path('export/', views.export_many),
    path('form/<str:level>/', views.form_definition),
    path('term-layouts/', tr.layouts),
    path('term/roster/', tr.roster),
    path('term/open/', tr.open_report),
    path('term/<uuid:pk>/', tr.report_detail),
    path('term/<uuid:pk>/prefill/', tr.report_prefill),
    path('term/<uuid:pk>/finalise/', tr.report_finalise),
    path('term/<uuid:pk>/reopen/', tr.report_reopen),
    path('<uuid:pk>/', views.record_detail),
    path('<uuid:pk>/export/', views.export_one),
    path('<uuid:pk>/years/<int:grade>/', views.year_save),
    path('<uuid:pk>/years/<int:grade>/prefill/', views.year_prefill),
    path('<uuid:pk>/years/<int:grade>/confirm/', views.year_confirm),
    path('<uuid:pk>/years/<int:grade>/reopen/', views.year_reopen),
]
