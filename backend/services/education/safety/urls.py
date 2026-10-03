from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('incidents', views.SafetyIncidentViewSet, basename='safety-incident')
router.register('follow-ups', views.FollowUpTaskViewSet, basename='follow-up-task')

urlpatterns = [
    path('', include(router.urls)),
]