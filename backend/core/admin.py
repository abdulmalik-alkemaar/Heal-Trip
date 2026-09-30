from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_active", "is_staff", "date_joined")
    search_fields = ("username", "email")

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": ("avatar_url",),
            },
        ),
    )
