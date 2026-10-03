from django.urls import path
from . import views
from . import push

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notification-list'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread-count'),
    path('mark-read/<uuid:pk>/', views.NotificationMarkReadView.as_view(), name='mark-read'),
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='mark-all-read'),

    # Push notifications (installed app)
    path('push/vapid-key/', push.vapid_key_view, name='push-vapid-key'),
    path('push/subscribe/', push.push_subscribe, name='push-subscribe'),
    path('push/unsubscribe/', push.push_unsubscribe, name='push-unsubscribe'),
    path('push/preferences/', push.push_preferences, name='push-preferences'),
    path('push/test/', push.push_test, name='push-test'),
    path('devices/', push.user_devices, name='user-devices'),
    path('devices/<uuid:device_id>/', push.remove_device, name='remove-device'),
]
