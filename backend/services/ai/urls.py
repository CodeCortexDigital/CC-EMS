from django.urls import include, path
from . import settings_api, teacher_tools, views

urlpatterns = [
    path("chat/", views.ai_chat, name="ai-chat"),
    path("chat/stream/", views.ai_chat_stream, name="ai-chat-stream"),
    path("conversations/", views.conversation_list, name="ai-conversations"),
    path("conversations/<uuid:conversation_id>/", views.conversation_detail, name="ai-conversation-detail"),
    path("messages/<uuid:message_id>/feedback/", views.message_feedback, name="ai-message-feedback"),
    # The school's AI settings and use notice (administrators)
    path("settings/", settings_api.ai_settings, name="ai-settings"),
    path("settings/accept-notice/", settings_api.accept_notice, name="ai-accept-notice"),
    path("capabilities/", settings_api.capabilities, name="ai-capabilities"),
    # Teacher assistant: drafts for the teacher to edit
    path("parent-message/", teacher_tools.ai_parent_message, name="ai-parent-message"),
    path("rubric/", teacher_tools.ai_rubric, name="ai-rubric"),
    # Lesson plans, quizzes, risk scans, face attendance
    path("", include("services.analytics.ai_urls")),
]
