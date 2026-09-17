from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "email", "department", "group_list", "is_active_employee", "is_active")
    list_filter = ("groups", "department", "is_active_employee", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Zoomart პროფილი", {"fields": ("department", "phone", "is_active_employee")}),
    )

    @admin.display(description="როლები")
    def group_list(self, obj):
        return ", ".join(obj.role_names) or "—"
