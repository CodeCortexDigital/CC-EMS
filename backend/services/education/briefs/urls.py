from django.urls import path

from . import views

urlpatterns = [
    path('today/', views.today, name='briefs-today'),
    path('generate/', views.generate, name='briefs-generate'),
    path('settings/', views.settings_view, name='briefs-settings'),
    path('rollups/', views.rollup_list, name='briefs-rollups'),
    path('rollups/generate/', views.rollup_generate, name='briefs-rollup-generate'),
    path('rollups/<uuid:pk>/', views.rollup_detail, name='briefs-rollup'),
    path('rollups/<uuid:pk>/approve/', views.rollup_approve, name='briefs-rollup-approve'),
    path('rollups/<uuid:pk>/read/', views.rollup_read, name='briefs-rollup-read'),
    path('<uuid:pk>/', views.daily_detail, name='briefs-detail'),
    path('<uuid:pk>/approve/', views.daily_approve, name='briefs-approve'),
    path('<uuid:pk>/read/', views.daily_read, name='briefs-read'),
    path('', views.daily_list, name='briefs-list'),
]
