from django.urls import path

from . import chosasho_views as cs
from . import standards_views as st
from . import transfer_views as tf
from . import termreport_views as tr
from . import views

urlpatterns = [
    path('roster/', views.roster),
    path('open/', views.open_record),
    path('export/', views.export_many),
    path('form/<str:level>/', views.form_definition),
    path('retention/', tf.retention_view),
    path('standards/', st.standards),
    path('external-ids/', st.external_ids),
    path('term-layouts/', tr.layouts),
    path('term/roster/', tr.roster),
    path('term/open/', tr.open_report),
    path('term/<uuid:pk>/', tr.report_detail),
    path('term/<uuid:pk>/prefill/', tr.report_prefill),
    path('term/<uuid:pk>/finalise/', tr.report_finalise),
    path('term/<uuid:pk>/reopen/', tr.report_reopen),
    path('<uuid:pk>/transfer/', tf.transfer),
    path('<uuid:pk>/transfer/<uuid:issue_id>/', tf.transfer_issue),
    path('<uuid:pk>/chosasho/', cs.chosasho_view),
    path('<uuid:pk>/chosasho/<uuid:issue_id>/', cs.chosasho_issue),
    path('<uuid:pk>/', views.record_detail),
    path('<uuid:pk>/export/', views.export_one),
    path('<uuid:pk>/years/<int:grade>/', views.year_save),
    path('<uuid:pk>/years/<int:grade>/prefill/', views.year_prefill),
    path('<uuid:pk>/years/<int:grade>/confirm/', views.year_confirm),
    path('<uuid:pk>/years/<int:grade>/reopen/', views.year_reopen),
]
