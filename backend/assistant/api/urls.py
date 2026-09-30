from django.urls import path

from . import views

urlpatterns = [
    path("chat/sessions/", views.SessionCreateView.as_view(), name="chat-session-create"),
    path(
        "chat/sessions/<uuid:session_id>/",
        views.SessionDetailView.as_view(),
        name="chat-session-detail",
    ),
    path(
        "chat/sessions/<uuid:session_id>/messages/",
        views.MessageCreateView.as_view(),
        name="chat-message-create",
    ),
]
