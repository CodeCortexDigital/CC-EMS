from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views, ext_api

router = DefaultRouter()
router.register('waitlist-configs', ext_api.WaitlistConfigViewSet, basename='waitlist-config')
router.register('waitlist-entries', ext_api.WaitlistEntryViewSet, basename='waitlist-entry')
router.register('offers', ext_api.OfferViewSet, basename='offer')
router.register('tour-slots', ext_api.TourSlotViewSet, basename='tour-slot')
router.register('tour-bookings', ext_api.TourBookingViewSet, basename='tour-booking')

urlpatterns = [
    # Public (no login): families answer offers, book tours, send documents and pay the fee with their tracking code
    path('public/offer/', ext_api.public_offer, name='admission-public-offer'),
    path('public/tours/', ext_api.public_tours, name='admission-public-tours'),
    path('public/tours/cancel/', ext_api.public_tours_cancel, name='admission-public-tours-cancel'),
    path('public/documents/', ext_api.public_documents, name='admission-public-documents'),
    path('public/fee/', ext_api.public_fee, name='admission-public-fee'),
    path('public/fee/checkout/', ext_api.public_fee_checkout, name='admission-public-fee-checkout'),
    # Public (no login)
    path('public/status/', views.public_status, name='admission-public-status'),
    path('public/<str:slug>/', views.public_form, name='admission-public-form'),
    path('public/<str:slug>/apply/', views.public_apply, name='admission-public-apply'),
    # School administrators
    path('settings/', views.admissions_settings, name='admission-settings'),
    path('applicants/', views.ApplicantListCreateView.as_view(), name='applicant-list'),
    path('applicants/<str:id>/', views.ApplicantDetailView.as_view(), name='applicant-detail'),
    path('applications/', views.ApplicationListCreateView.as_view(), name='application-list'),
    path('applications/<str:id>/', views.ApplicationDetailView.as_view(), name='application-detail'),
    path('applications/<str:id>/update-status/', views.update_application_status, name='update-status'),
    path('applications/<str:id>/notes/', views.add_note, name='application-notes'),
    path('applications/<str:id>/ai-screen/', views.ai_screen_application, name='application-ai-screen'),
    path('applications/<str:id>/documents/', views.upload_documents, name='application-documents'),
    path('applications/<str:id>/documents/<str:doc_id>/', views.delete_document, name='application-document'),
    path('applications/<str:id>/documents/<str:doc_id>/review/', ext_api.review_document, name='application-document-review'),
    path('applications/<str:id>/checklist/', ext_api.application_checklist, name='application-checklist'),
    path('applications/<str:id>/fee/waive/', ext_api.fee_waive, name='application-fee-waive'),
    path('applications/<str:id>/fee/mark-paid/', ext_api.fee_mark_paid, name='application-fee-paid'),
    path('applications/<str:id>/convert-to-student/', views.convert_to_student, name='convert-to-student'),
    path('applications/<str:id>/enroll/', views.convert_to_student, name='application-enroll'),
    # Re-enrolment
    path('reenrollment/', views.reenrollment_campaigns, name='reenrollment-list'),
    path('reenrollment/mine/', views.my_reenrollments, name='reenrollment-mine'),
    path('reenrollment/responses/<str:id>/', views.reenrollment_record, name='reenrollment-record'),
    path('reenrollment/responses/<str:id>/respond/', views.respond_reenrollment, name='reenrollment-respond'),
    path('reenrollment/<str:id>/', views.reenrollment_campaign_detail, name='reenrollment-detail'),
    path('', include(router.urls)),
]
