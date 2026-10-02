from django.urls import path

from . import api, pack_api

urlpatterns = [
    path('', api.kinds, name='imports-kinds'),
    path('pack/spec/', pack_api.pack_spec, name='imports-pack-spec'),
    path('pack/template/', pack_api.pack_template, name='imports-pack-template'),
    path('pack/export/', pack_api.pack_export, name='imports-pack-export'),
    path('pack/preview/', pack_api.pack_preview, name='imports-pack-preview'),
    path('pack/import/', pack_api.pack_import, name='imports-pack-import'),
    path('pack/jobs/<uuid:job_id>/', pack_api.pack_job, name='imports-pack-job'),
    path('history/', api.history, name='imports-history'),
    path('history/<uuid:run_id>/problems.csv', api.problems_csv, name='imports-problems'),
    path('<str:kind>/template/', api.template, name='imports-template'),
    path('<str:kind>/export/', api.export_kind, name='imports-export'),
    path('<str:kind>/preview/', api.preview, name='imports-preview'),
    path('<str:kind>/import/', api.commit, name='imports-commit'),
]
