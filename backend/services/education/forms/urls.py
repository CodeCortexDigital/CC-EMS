from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('templates', views.FormTemplateViewSet, basename='form-template')
router.register('my', views.MyFormsViewSet, basename='my-form')

urlpatterns = [
    path('', include(router.urls)),
]
