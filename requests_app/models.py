import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from auditlog.registry import auditlog

from core.models import ApprovalStepRule, Department, RequestCategory


def attachment_upload_path(instance, filename):
    return f"requests/{instance.request.request_number}/{uuid.uuid4().hex}_{filename}"


class Request(models.Model):
    STATUS_DRAFT = "DRAFT"
    STATUS_SUBMITTED = "SUBMITTED"
    STATUS_PENDING_MANAGER = "PENDING_MANAGER_APPROVAL"
    STATUS_MORE_INFO = "MORE_INFO_REQUIRED"
    STATUS_MANAGER_APPROVED = "MANAGER_APPROVED"
    STATUS_PENDING_FINANCE = "PENDING_FINANCE_REVIEW"
    STATUS_PENDING_SENIOR = "PENDING_SENIOR_APPROVAL"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_PURCHASE_IN_PROGRESS = "PURCHASE_IN_PROGRESS"
    STATUS_PURCHASED = "PURCHASED"
    STATUS_PAID = "PAID"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "მონახაზი"),
        (STATUS_SUBMITTED, "გაგზავნილი"),
        (STATUS_PENDING_MANAGER, "დეპარტამენტის დირექტორის დამტკიცების მოლოდინში"),
        (STATUS_MORE_INFO, "საჭიროა დამატებითი ინფორმაცია"),
        (STATUS_MANAGER_APPROVED, "დეპარტამენტის დირექტორმა დაამტკიცა"),
        (STATUS_PENDING_FINANCE, "ფინანსების განხილვის მოლოდინში"),
        (STATUS_PENDING_SENIOR, "კომპანიის დირექტორის დამტკიცების მოლოდინში"),
        (STATUS_APPROVED, "დამტკიცებული"),
        (STATUS_REJECTED, "უარყოფილი"),
        (STATUS_PURCHASE_IN_PROGRESS, "შესყიდვა მიმდინარეობს"),
        (STATUS_PURCHASED, "შეძენილი"),
        (STATUS_PAID, "გადახდილი"),
        (STATUS_COMPLETED, "დასრულებული"),
        (STATUS_CANCELLED, "გაუქმებული"),
    ]

    OPEN_STATUSES = [
        STATUS_SUBMITTED, STATUS_PENDING_MANAGER, STATUS_MORE_INFO,
        STATUS_MANAGER_APPROVED, STATUS_PENDING_FINANCE, STATUS_PENDING_SENIOR,
    ]
    STATUS_COLORS = {
        STATUS_DRAFT: "gray",
        STATUS_SUBMITTED: "yellow",
        STATUS_PENDING_MANAGER: "yellow",
        STATUS_MORE_INFO: "orange",
        STATUS_MANAGER_APPROVED: "yellow",
        STATUS_PENDING_FINANCE: "yellow",
        STATUS_PENDING_SENIOR: "yellow",
        STATUS_APPROVED: "green",
        STATUS_REJECTED: "red",
        STATUS_PURCHASE_IN_PROGRESS: "blue",
        STATUS_PURCHASED: "blue",
        STATUS_PAID: "blue",
        STATUS_COMPLETED: "blue",
        STATUS_CANCELLED: "gray",
    }

    PRIORITY_LOW = "LOW"
    PRIORITY_MEDIUM = "MEDIUM"
    PRIORITY_HIGH = "HIGH"
    PRIORITY_URGENT = "URGENT"
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, "დაბალი"),
        (PRIORITY_MEDIUM, "საშუალო"),
        (PRIORITY_HIGH, "მაღალი"),
        (PRIORITY_URGENT, "სასწრაფო"),
    ]

    CURRENCY_CHOICES = [("GEL", "GEL"), ("USD", "USD"), ("EUR", "EUR")]

    REQUEST_TYPE_CHOICES = [
        ("PURCHASE", "შესყიდვა"),
        ("SERVICE", "სერვისი"),
        ("SUBSCRIPTION", "გამოწერა / პროგრამული უზრუნველყოფა"),
        ("REPAIR_MAINTENANCE", "შეკეთება / ტექმომსახურება"),
        ("OTHER", "სხვა"),
    ]

    request_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requests"
    )
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="requests", null=True, blank=True,
        help_text="ცარიელი დატოვება შესაძლებელია კომპანიის დირექტორისა და სხვა კომპანიის მასშტაბის როლებისთვის.",
    )
    category = models.ForeignKey(RequestCategory, on_delete=models.PROTECT, related_name="requests")
    request_type = models.CharField(max_length=32, choices=REQUEST_TYPE_CHOICES, default="PURCHASE")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default="GEL")
    quantity = models.PositiveIntegerField(default=1)

    vendor_name = models.CharField(max_length=200, blank=True)
    vendor_url = models.URLField(blank=True)
    product_url = models.URLField(blank=True)

    required_by_date = models.DateField(null=True, blank=True)
    business_justification = models.TextField()
    notes = models.TextField(blank=True)
    is_confidential = models.BooleanField(
        default=False,
        help_text="Only the requester, assigned approvers, Administrators and Senior Management can view a confidential request.",
    )

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requests_to_approve",
    )
    current_approver_role = models.CharField(max_length=32, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "მოთხოვნა"
        verbose_name_plural = "მოთხოვნები"

    def __str__(self):
        return f"{self.request_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.request_number:
            self.request_number = self._generate_request_number()
        super().save(*args, **kwargs)

    def _generate_request_number(self):
        # Encodes the actual creation date (not just the year) so the
        # number itself tells you when a request was made — e.g.
        # REQ-20260919-001. The sequence resets each day.
        today = timezone.now().strftime("%Y%m%d")
        prefix = f"REQ-{today}-"
        last = (
            Request.objects.filter(request_number__startswith=prefix)
            .order_by("-request_number")
            .first()
        )
        next_seq = 1
        if last:
            try:
                next_seq = int(last.request_number.split("-")[-1]) + 1
            except ValueError:
                next_seq = Request.objects.filter(request_number__startswith=prefix).count() + 1
        return f"{prefix}{next_seq:03d}"

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, "gray")

    @property
    def is_editable(self):
        return self.status in (self.STATUS_DRAFT, self.STATUS_MORE_INFO)

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES


class RequestAttachment(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to=attachment_upload_path,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png", "xlsx", "docx"])],
    )
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "დანართი"
        verbose_name_plural = "დანართები"

    def __str__(self):
        return self.original_filename

    def clean(self):
        max_bytes = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
        if self.file and self.file.size > max_bytes:
            raise ValidationError(f"File too large (max {settings.MAX_ATTACHMENT_SIZE_MB} MB).")
        ext = os.path.splitext(self.file.name)[1].lower()
        if ext not in settings.ALLOWED_ATTACHMENT_EXTENSIONS:
            raise ValidationError(f"File type '{ext}' is not allowed.")


class RequestComment(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "კომენტარი"
        verbose_name_plural = "კომენტარები"

    def __str__(self):
        return f"Comment by {self.author} on {self.request}"


class RequestApprovalQuerySet(models.QuerySet):
    def pending_for_user(self, user):
        if not user.is_authenticated:
            return self.none()
        qs = self.filter(decision=RequestApproval.DECISION_PENDING)
        role_q = models.Q(assigned_to=user)
        if user.has_role("Finance"):
            role_q |= models.Q(approver_role=ApprovalStepRuleRoleMirror.FINANCE, assigned_to__isnull=True)
        if user.has_role("Senior Management"):
            role_q |= models.Q(approver_role=ApprovalStepRuleRoleMirror.SENIOR_MANAGER, assigned_to__isnull=True)
        return qs.filter(role_q).select_related("request")


class ApprovalStepRuleRoleMirror:
    """Tiny helper so this module doesn't need a hard import cycle with core.models."""
    DEPARTMENT_MANAGER = "DEPARTMENT_MANAGER"
    FINANCE = "FINANCE"
    SENIOR_MANAGER = "SENIOR_MANAGER"
    SPECIFIC_USER = "SPECIFIC_USER"


class RequestApproval(models.Model):
    """One row per required approval step for a given request (its 'timeline')."""

    DECISION_NOT_STARTED = "NOT_STARTED"
    DECISION_PENDING = "PENDING"
    DECISION_APPROVED = "APPROVED"
    DECISION_REJECTED = "REJECTED"
    DECISION_INFO_REQUESTED = "INFO_REQUESTED"
    DECISION_SKIPPED = "SKIPPED"
    DECISION_CHOICES = [
        (DECISION_NOT_STARTED, "არ დაწყებულა"),
        (DECISION_PENDING, "მოლოდინში"),
        (DECISION_APPROVED, "დამტკიცებული"),
        (DECISION_REJECTED, "უარყოფილი"),
        (DECISION_INFO_REQUESTED, "მოთხოვნილია დამატებითი ინფორმაცია"),
        (DECISION_SKIPPED, "გამოტოვებული"),
    ]

    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name="approval_steps")
    step_order = models.PositiveIntegerField()
    approver_role = models.CharField(max_length=32, choices=ApprovalStepRule.ROLE_CHOICES)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_assignments",
    )
    decision = models.CharField(max_length=16, choices=DECISION_CHOICES, default=DECISION_NOT_STARTED)
    comment = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = RequestApprovalQuerySet.as_manager()

    class Meta:
        ordering = ["request", "step_order"]
        verbose_name = "დამტკიცების საფეხური"
        verbose_name_plural = "დამტკიცების ისტორია"

    def __str__(self):
        return f"{self.request.request_number} step {self.step_order} ({self.approver_role})"


class PaymentDetail(models.Model):
    request = models.OneToOneField(Request, on_delete=models.CASCADE, related_name="payment_detail")
    actual_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    payment_date = models.DateField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "გადახდის დეტალი"
        verbose_name_plural = "გადახდის დეტალები"

    def __str__(self):
        return f"Payment detail for {self.request.request_number}"


auditlog.register(Request)
auditlog.register(RequestAttachment)
auditlog.register(RequestComment)
auditlog.register(RequestApproval)
auditlog.register(PaymentDetail)
