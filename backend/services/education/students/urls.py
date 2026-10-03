from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, pickup_api, health_api, lookup_api

router = DefaultRouter()
router.register('certificates', views.CertificateViewSet, basename='certificate')
# Front desk
router.register('authorized-adults', pickup_api.AuthorizedAdultViewSet, basename='authorized-adult')
router.register('pickup-releases', pickup_api.PickupReleaseViewSet, basename='pickup-release')
router.register('visitors', pickup_api.VisitorLogViewSet, basename='visitor-log')
# Health office
router.register('health-visits', health_api.HealthVisitViewSet, basename='health-visit')
router.register('medication-authorizations', health_api.MedicationAuthorizationViewSet, basename='medication-authorization')
router.register('medication-logs', health_api.MedicationLogViewSet, basename='medication-log')

urlpatterns = [
    path('', include(router.urls)),
    path('pickup-list/', pickup_api.pickup_list, name='pickup-list'),
    path('lookup/', lookup_api.student_lookup, name='student-lookup'),
    path('<str:id>/force-activity/', views.force_update_activity, name='force-activity'),
    path('<str:id>/update-activity/', views.update_student_activity, name='update-activity'),
    path('last-registration/', views.last_registration, name='student-last-registration'),
    path('', views.StudentListCreateView.as_view(), name='student-list'),
    path('<str:id>/', views.StudentDetailView.as_view(), name='student-detail'),
    path('by-id/<str:student_id>/', views.get_student_by_id, name='student-by-id'),
    path('student-360/<str:student_id>/', views.student_360, name='student-360'),
]
