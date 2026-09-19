"""
Approval-step email notifications.

Intentionally narrow: we email a director only at the exact moment their
own approval becomes the thing blocking the request — never on submission
itself, and never for Finance or Procurement Manager (they were not asked
for). If sending fails for any reason (no SMTP configured yet, bad network,
etc.) we log it and swallow the error — a notification problem must never
break someone's ability to submit or approve a request.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from core.models import ApprovalStepRule

logger = logging.getLogger(__name__)

SUBJECT_KA = "მოთხოვნა {number} ელოდება თქვენს დამტკიცებას — ZooFlow"

BODY_KA = """გამარჯობა,

მოთხოვნა {number} ({title}) ახლა თქვენს დამტკიცებას ელოდება.

მომთხოვნელი: {requester}
დეპარტამენტი: {department}
თანხა: {amount} {currency}

ნახეთ და გადაწყვიტეთ აქ:
{link}

ეს არის ავტომატური შეტყობინება ZooFlow-დან — Zoomart-ის ხარჯებისა და მოთხოვნების სისტემა.
"""


def _send(*, to_emails, request_obj):
    to_emails = [e for e in to_emails if e]
    if not to_emails:
        return
    link = f"{settings.SITE_URL.rstrip('/')}/requests/{request_obj.pk}/"
    body = BODY_KA.format(
        number=request_obj.request_number,
        title=request_obj.title,
        requester=str(request_obj.requester),
        department=str(request_obj.department),
        amount=request_obj.estimated_cost,
        currency=request_obj.currency,
        link=link,
    )
    try:
        send_mail(
            SUBJECT_KA.format(number=request_obj.request_number),
            body,
            settings.DEFAULT_FROM_EMAIL,
            to_emails,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send approval-step notification email for %s", request_obj.request_number)


def notify_step_activated(request_obj, step):
    """Call right after `step` becomes the active (PENDING) approval step.

    Emails only the department director or the company director, and only
    when it is genuinely their turn to act — not on submission, not for
    every step.
    """
    if step.approver_role == ApprovalStepRule.ROLE_DEPARTMENT_MANAGER:
        if step.assigned_to and step.assigned_to.email:
            _send(to_emails=[step.assigned_to.email], request_obj=request_obj)
    elif step.approver_role == ApprovalStepRule.ROLE_SENIOR_MANAGER:
        User = get_user_model()
        emails = list(
            User.objects.filter(groups__name="Senior Management", is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
            .distinct()
        )
        _send(to_emails=emails, request_obj=request_obj)
