from django.conf import settings
from django.db import models
from auditlog.registry import auditlog


class Department(models.Model):
    name = models.CharField(max_length=120, unique=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="managed_departments",
        help_text="ეს პირია ამ დეპარტამენტის 'დეპარტამენტის დირექტორი' — ამტკიცებს ამ დეპარტამენტის მოთხოვნებს (თუ თავად არის მომთხოვნელი, ეს საფეხური ავტომატურად გამოტოვდება).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "დეპარტამენტი"
        verbose_name_plural = "დეპარტამენტები"

    def __str__(self):
        return self.name


class RequestCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "კატეგორია"
        verbose_name_plural = "მოთხოვნის კატეგორიები"

    def __str__(self):
        return self.name


class ApprovalWorkflowRule(models.Model):
    """
    A configurable rule: "if the request's amount falls in [min,max] (and
    optionally matches a department/category), use this ordered chain of
    approval steps." Administrator manages these; nothing is hardcoded.
    """

    name = models.CharField(max_length=150)
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Leave empty to apply to all departments.",
    )
    category = models.ForeignKey(
        RequestCategory,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Leave empty to apply to all categories.",
    )
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Leave empty for 'and above'.",
    )
    is_active = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(
        default=0,
        help_text="When several rules match, the highest priority (larger number) wins.",
    )

    class Meta:
        ordering = ["-priority", "min_amount"]
        verbose_name = "დამტკიცების წესი"
        verbose_name_plural = "დამტკიცების წესები"

    def __str__(self):
        top = f"{self.max_amount}" if self.max_amount is not None else "+"
        return f"{self.name} ({self.min_amount}-{top} GEL)"

    def matches(self, *, amount, department_id, category_id):
        if not self.is_active:
            return False
        if self.department_id and self.department_id != department_id:
            return False
        if self.category_id and self.category_id != category_id:
            return False
        if amount < self.min_amount:
            return False
        if self.max_amount is not None and amount > self.max_amount:
            return False
        return True


class ApprovalStepRule(models.Model):
    ROLE_DEPARTMENT_MANAGER = "DEPARTMENT_MANAGER"
    ROLE_PROCUREMENT_MANAGER = "PROCUREMENT_MANAGER"
    ROLE_FINANCE = "FINANCE"
    ROLE_SENIOR_MANAGER = "SENIOR_MANAGER"
    ROLE_SPECIFIC_USER = "SPECIFIC_USER"
    ROLE_CHOICES = [
        (ROLE_DEPARTMENT_MANAGER, "დეპარტამენტის დირექტორი"),
        (ROLE_PROCUREMENT_MANAGER, "შესყიდვების მენეჯერი"),
        (ROLE_FINANCE, "ფინანსები"),
        (ROLE_SENIOR_MANAGER, "კომპანიის დირექტორი"),
        (ROLE_SPECIFIC_USER, "კონკრეტული პირი"),
    ]

    workflow_rule = models.ForeignKey(
        ApprovalWorkflowRule, on_delete=models.CASCADE, related_name="steps"
    )
    order = models.PositiveIntegerField(help_text="1 = first approver, 2 = second, ...")
    approver_role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    specific_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Only used when 'approver role' is 'Specific person'.",
    )

    class Meta:
        ordering = ["workflow_rule", "order"]
        unique_together = ("workflow_rule", "order")
        verbose_name = "დამტკიცების საფეხური"
        verbose_name_plural = "დამტკიცების საფეხურები"

    def __str__(self):
        return f"საფეხური {self.order}: {self.get_approver_role_display()}"


auditlog.register(Department)
auditlog.register(RequestCategory)
auditlog.register(ApprovalWorkflowRule)
auditlog.register(ApprovalStepRule)
