from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from core.templatetags.ka_labels import role_ka
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Advanced/fallback screen — day-to-day adding of people, roles and
    department directors happens on the simpler 'გუნდის მართვა' page
    (/management/team/). This stays available for anything that page
    doesn't cover yet (raw permission tweaks, bulk actions, etc.).
    """

    list_display = ("username", "get_full_name", "email", "department", "group_list", "is_active_employee", "is_active")
    list_filter = ("groups", "department", "is_active_employee", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("პირადი ინფორმაცია", {"fields": ("first_name", "last_name", "email")}),
        ("Zoomart პროფილი", {"fields": ("department", "phone", "is_active_employee")}),
        (
            "წვდომები და როლები (გაფრთხილება: ცვლილება პირდაპირ აქედან არ ააქტიურებს დეპარტამენტის დირექტორის ავტომატურ დანიშვნას — ამისთვის გამოიყენეთ 'გუნდის მართვა')",
            {"classes": ("collapse",), "fields": ("groups", "is_active", "is_staff", "is_superuser", "user_permissions")},
        ),
        ("სისტემური ინფორმაცია", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )

    @admin.display(description="როლები")
    def group_list(self, obj):
        return ", ".join(role_ka(r) for r in obj.role_names) or "—"
