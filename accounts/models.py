from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user. Roles are modeled with Django's built-in Group system
    (Employee / Manager / Finance / Administrator / Senior Management),
    so new roles can be added later from Admin without code changes.
    """

    department = models.ForeignKey(
        "core.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
        help_text="The department this employee belongs to.",
    )
    phone = models.CharField(max_length=32, blank=True)
    is_active_employee = models.BooleanField(
        default=True,
        help_text="Administrator can deactivate a user without deleting their history.",
    )

    def __str__(self):
        full = self.get_full_name()
        return full if full else self.username

    def has_role(self, role_name: str) -> bool:
        return self.groups.filter(name=role_name).exists()

    @property
    def role_names(self):
        return list(self.groups.values_list("name", flat=True))

    @property
    def is_manager(self):
        return self.has_role("Manager")

    @property
    def is_finance(self):
        return self.has_role("Finance")

    @property
    def is_admin_role(self):
        return self.has_role("Administrator") or self.is_superuser

    @property
    def is_senior_management(self):
        return self.has_role("Senior Management")

    @property
    def is_employee(self):
        return self.has_role("Employee")
