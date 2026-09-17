from django.contrib import admin

from .models import ApprovalStepRule, ApprovalWorkflowRule, Department, RequestCategory


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "manager", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(RequestCategory)
class RequestCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")


class ApprovalStepRuleInline(admin.TabularInline):
    model = ApprovalStepRule
    extra = 1
    fields = ("order", "approver_role", "specific_user")


@admin.register(ApprovalWorkflowRule)
class ApprovalWorkflowRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "category", "min_amount", "max_amount", "priority", "is_active")
    list_filter = ("is_active", "department", "category")
    inlines = [ApprovalStepRuleInline]
