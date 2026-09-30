from django.contrib import admin

from .models import AgentRunLog, ChatSession, Message, ToolCallLog


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("role", "content", "created_at")
    readonly_fields = fields
    can_delete = False


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "language",
        "current_stage",
        "urgency_level",
        "clarification_rounds",
        "user",
        "updated_at",
    )
    list_filter = ("language", "current_stage", "urgency_level")
    search_fields = ("id",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("session", "role", "short_content", "created_at")
    list_filter = ("role",)
    search_fields = ("session__id",)

    @admin.display(description="Content")
    def short_content(self, obj: Message) -> str:
        return obj.content[:80]


@admin.register(AgentRunLog)
class AgentRunLogAdmin(admin.ModelAdmin):
    list_display = (
        "session",
        "outcome",
        "final_urgency",
        "urgency_source",
        "next_step",
        "iterations",
        "latency_ms",
        "grounding_violations_count",
        "created_at",
    )
    list_filter = ("outcome", "final_urgency", "urgency_source", "next_step", "llm_provider")
    search_fields = ("session__id",)


@admin.register(ToolCallLog)
class ToolCallLogAdmin(admin.ModelAdmin):
    list_display = ("session", "tool_name", "success", "result_ids", "latency_ms", "created_at")
    list_filter = ("tool_name", "success")
    search_fields = ("session__id",)
