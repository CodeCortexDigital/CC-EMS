from django.urls import include, path
from . import governance_api, settings_api, teacher_tools, views

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
    # Governed AI: approvals for what the assistant asks to do, and the school documents it may quote
    path("governance/actions/", governance_api.action_list, name="ai-gov-actions"),
    path("governance/approvals/", governance_api.approval_list, name="ai-gov-approvals"),
    path("governance/requests/fee-reminder/", governance_api.request_fee_reminder, name="ai-gov-request-fee-reminder"),
    path("governance/records/", governance_api.record_list, name="ai-gov-records"),
    path("governance/records/<int:seq>/", governance_api.record_detail, name="ai-gov-record-entry"),
    path("governance/approvals/<uuid:pk>/record/", governance_api.approval_record, name="ai-gov-record"),
    path("governance/approvals/<uuid:pk>/approve/", governance_api.approval_approve, name="ai-gov-approve"),
    path("governance/approvals/<uuid:pk>/settle/", governance_api.approval_settle, name="ai-gov-settle"),
    path("governance/approvals/<uuid:pk>/reject/", governance_api.approval_reject, name="ai-gov-reject"),
    path("governance/knowledge/", governance_api.knowledge_list, name="ai-gov-knowledge"),
    path("governance/knowledge/search/", governance_api.knowledge_search, name="ai-gov-knowledge-search"),
    path("governance/knowledge/<uuid:pk>/", governance_api.knowledge_detail, name="ai-gov-knowledge-detail"),
    # Teacher assistant: drafts for the teacher to edit
    path("parent-message/", teacher_tools.ai_parent_message, name="ai-parent-message"),
    path("rubric/", teacher_tools.ai_rubric, name="ai-rubric"),
    # Lesson plans, quizzes, risk scans, face attendance
    path("", include("services.analytics.ai_urls")),
]
