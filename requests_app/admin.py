from django.contrib import admin

from .models import PaymentDetail, Request, RequestApproval, RequestAttachment, RequestComment


class RequestApprovalInline(admin.TabularInline):
    model = RequestApproval
    extra = 0
    readonly_fields = ("step_order", "approver_role", "assigned_to", "decision", "comment", "decided_by", "decided_at")
    can_delete = False


class RequestAttachmentInline(admin.TabularInline):
    model = RequestAttachment
    extra = 0
    readonly_fields = ("original_filename", "uploaded_by", "uploaded_at")
    can_delete = False


class RequestCommentInline(admin.TabularInline):
    model = RequestComment
    extra = 0
    readonly_fields = ("author", "message", "created_at")
    can_delete = False


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_number", "title", "requester", "department", "category",
        "status", "priority", "estimated_cost", "currency", "created_at",
    )
    list_filter = ("status", "department", "category", "priority", "currency")
    search_fields = ("request_number", "title", "requester__username", "vendor_name")
    readonly_fields = ("request_number", "created_at", "updated_at", "submitted_at")
    inlines = [RequestApprovalInline, RequestAttachmentInline, RequestCommentInline]


@admin.register(PaymentDetail)
class PaymentDetailAdmin(admin.ModelAdmin):
    list_display = ("request", "actual_amount", "invoice_number", "payment_date", "recorded_by")
