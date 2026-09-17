"""
ApprovalEngineService — all approval-workflow business logic lives here,
deliberately kept out of views/templates so it can be unit-tested and
reused (e.g. later from an API for n8n).
"""

from django.db import transaction
from django.utils import timezone

from core.models import ApprovalStepRule, ApprovalWorkflowRule
from .models import Request, RequestApproval

STATUS_FOR_ROLE = {
    ApprovalStepRule.ROLE_DEPARTMENT_MANAGER: Request.STATUS_PENDING_MANAGER,
    ApprovalStepRule.ROLE_FINANCE: Request.STATUS_PENDING_FINANCE,
    ApprovalStepRule.ROLE_SENIOR_MANAGER: Request.STATUS_PENDING_SENIOR,
    ApprovalStepRule.ROLE_SPECIFIC_USER: Request.STATUS_PENDING_MANAGER,
}


class ApprovalError(Exception):
    """Raised for any rule violation — views turn this into a user-facing message."""


def get_matching_rule(*, amount, department_id, category_id):
    candidates = ApprovalWorkflowRule.objects.filter(is_active=True).prefetch_related("steps")
    matched = [
        r for r in candidates
        if r.matches(amount=amount, department_id=department_id, category_id=category_id)
    ]
    if not matched:
        return None
    matched.sort(key=lambda r: r.priority, reverse=True)
    return matched[0]


def _resolve_assigned_to(step, request_obj):
    if step.approver_role == ApprovalStepRule.ROLE_DEPARTMENT_MANAGER:
        return request_obj.department.manager
    if step.approver_role == ApprovalStepRule.ROLE_SPECIFIC_USER:
        return step.specific_user
    return None  # FINANCE / SENIOR_MANAGER: any user with that role/group may act


def _build_steps(request_obj, rule):
    request_obj.approval_steps.all().delete()
    steps = []
    for step_rule in rule.steps.order_by("order"):
        steps.append(
            RequestApproval(
                request=request_obj,
                step_order=step_rule.order,
                approver_role=step_rule.approver_role,
                assigned_to=_resolve_assigned_to(step_rule, request_obj),
            )
        )
    RequestApproval.objects.bulk_create(steps)


def _activate_next_step(request_obj):
    """Point the request at its next step (activating it: Not Started -> Pending), or finalize as Approved."""
    next_step = (
        request_obj.approval_steps.filter(
            decision__in=[RequestApproval.DECISION_NOT_STARTED, RequestApproval.DECISION_PENDING]
        )
        .order_by("step_order")
        .first()
    )
    if next_step is not None and next_step.decision == RequestApproval.DECISION_NOT_STARTED:
        next_step.decision = RequestApproval.DECISION_PENDING
        next_step.save()
    if next_step is None:
        request_obj.status = Request.STATUS_APPROVED
        request_obj.current_approver = None
        request_obj.current_approver_role = ""
    else:
        request_obj.status = STATUS_FOR_ROLE.get(next_step.approver_role, Request.STATUS_PENDING_MANAGER)
        request_obj.current_approver = next_step.assigned_to
        request_obj.current_approver_role = next_step.approver_role
    request_obj.save()


def submit_request(request_obj, actor):
    if request_obj.requester_id != actor.id and not actor.is_admin_role:
        raise ApprovalError("მხოლოდ მომთხოვნელს (ან ადმინისტრატორს) შეუძლია ამ მოთხოვნის გაგზავნა.")
    if request_obj.status not in (Request.STATUS_DRAFT, Request.STATUS_MORE_INFO):
        raise ApprovalError("გაგზავნა შესაძლებელია მხოლოდ 'მონახაზი' ან 'საჭიროა დამატებითი ინფორმაცია' სტატუსში მყოფი მოთხოვნისთვის.")
    if request_obj.department.manager_id is None:
        raise ApprovalError(
            f"დეპარტამენტს '{request_obj.department}' ჯერ არ ჰყავს დანიშნული მენეჯერი — "
            "სთხოვეთ ადმინისტრატორს, დანიშნოს მენეჯერი სანამ ეს მოთხოვნა გაიგზავნება."
        )

    with transaction.atomic():
        if request_obj.status == Request.STATUS_DRAFT:
            rule = get_matching_rule(
                amount=request_obj.estimated_cost,
                department_id=request_obj.department_id,
                category_id=request_obj.category_id,
            )
            if not rule:
                raise ApprovalError(
                    "ამ მოთხოვნის თანხას/დეპარტამენტს/კატეგორიას ვერცერთი დამტკიცების წესი ვერ ესადაგება. "
                    "სთხოვეთ ადმინისტრატორს, დააკონფიგურიროს წესი: ადმინისტრირება → დამტკიცების წესები."
                )
            _build_steps(request_obj, rule)
            request_obj.submitted_at = timezone.now()
        else:
            # Returning from "More Information Required": reopen the step that asked for it.
            pending_step = (
                request_obj.approval_steps.filter(decision=RequestApproval.DECISION_INFO_REQUESTED)
                .order_by("step_order")
                .first()
            )
            if pending_step:
                pending_step.decision = RequestApproval.DECISION_PENDING
                pending_step.decided_by = None
                pending_step.decided_at = None
                pending_step.save()

        request_obj.status = Request.STATUS_SUBMITTED
        request_obj.save()
        _activate_next_step(request_obj)

    return request_obj


ROLE_GROUP_LABELS_KA = {
    "Finance": "ფინანსები",
    "Senior Management": "უფროსი მენეჯმენტი",
}


def _authorize_actor_for_step(request_obj, step, actor):
    if request_obj.requester_id == actor.id:
        raise ApprovalError("თქვენ ვერ დაამტკიცებთ, ვერ უარყოფთ და ვერ იმოქმედებთ საკუთარ მოთხოვნაზე.")
    if actor.is_admin_role:
        return
    if step.assigned_to_id:
        if actor.id != step.assigned_to_id:
            raise ApprovalError("თქვენ არ ხართ ამ საფეხურზე დანიშნული დამტკიცებელი.")
        return
    role_group = {
        ApprovalStepRule.ROLE_FINANCE: "Finance",
        ApprovalStepRule.ROLE_SENIOR_MANAGER: "Senior Management",
    }.get(step.approver_role)
    if role_group and not actor.has_role(role_group):
        raise ApprovalError(f"ეს საფეხური მოითხოვს '{ROLE_GROUP_LABELS_KA.get(role_group, role_group)}' როლს.")


def _current_pending_step(request_obj):
    step = (
        request_obj.approval_steps.select_for_update()
        .filter(decision=RequestApproval.DECISION_PENDING)
        .order_by("step_order")
        .first()
    )
    if not step:
        raise ApprovalError("ამ მოთხოვნას ამჟამად არ აქვს დასამტკიცებელი საფეხური (შესაძლოა უკვე გადაწყვეტილია).")
    return step


def approve(request_obj, actor, comment=""):
    with transaction.atomic():
        request_obj = Request.objects.select_for_update().get(pk=request_obj.pk)
        if request_obj.status not in STATUS_FOR_ROLE.values():
            raise ApprovalError("ეს მოთხოვნა ამჟამად არ არის დამტკიცების მოლოდინში.")
        step = _current_pending_step(request_obj)
        _authorize_actor_for_step(request_obj, step, actor)
        step.decision = RequestApproval.DECISION_APPROVED
        step.comment = comment
        step.decided_by = actor
        step.decided_at = timezone.now()
        step.save()
        _activate_next_step(request_obj)
    return request_obj


def reject(request_obj, actor, comment):
    if not comment or not comment.strip():
        raise ApprovalError("მოთხოვნის უარსაყოფად კომენტარი სავალდებულოა.")
    with transaction.atomic():
        request_obj = Request.objects.select_for_update().get(pk=request_obj.pk)
        step = _current_pending_step(request_obj)
        _authorize_actor_for_step(request_obj, step, actor)
        step.decision = RequestApproval.DECISION_REJECTED
        step.comment = comment
        step.decided_by = actor
        step.decided_at = timezone.now()
        step.save()
        request_obj.approval_steps.filter(decision__in=[RequestApproval.DECISION_PENDING, RequestApproval.DECISION_NOT_STARTED]).update(
            decision=RequestApproval.DECISION_SKIPPED
        )
        request_obj.status = Request.STATUS_REJECTED
        request_obj.current_approver = None
        request_obj.current_approver_role = ""
        request_obj.save()
    return request_obj


def request_more_info(request_obj, actor, comment):
    if not comment or not comment.strip():
        raise ApprovalError("დამატებითი ინფორმაციის მოთხოვნისთვის კომენტარი სავალდებულოა.")
    with transaction.atomic():
        request_obj = Request.objects.select_for_update().get(pk=request_obj.pk)
        step = _current_pending_step(request_obj)
        _authorize_actor_for_step(request_obj, step, actor)
        step.decision = RequestApproval.DECISION_INFO_REQUESTED
        step.comment = comment
        step.decided_by = actor
        step.decided_at = timezone.now()
        step.save()
        request_obj.status = Request.STATUS_MORE_INFO
        request_obj.current_approver = request_obj.requester
        request_obj.current_approver_role = "EMPLOYEE"
        request_obj.save()
    return request_obj


def cancel(request_obj, actor):
    if request_obj.requester_id != actor.id and not actor.is_admin_role:
        raise ApprovalError("მხოლოდ მომთხოვნელს (ან ადმინისტრატორს) შეუძლია ამ მოთხოვნის გაუქმება.")
    if request_obj.status in (Request.STATUS_COMPLETED, Request.STATUS_PAID, Request.STATUS_REJECTED, Request.STATUS_CANCELLED):
        raise ApprovalError("ამ მოთხოვნის გაუქმება ვეღარ ხერხდება.")
    with transaction.atomic():
        request_obj = Request.objects.select_for_update().get(pk=request_obj.pk)
        request_obj.approval_steps.filter(decision__in=[RequestApproval.DECISION_PENDING, RequestApproval.DECISION_NOT_STARTED]).update(
            decision=RequestApproval.DECISION_SKIPPED
        )
        request_obj.status = Request.STATUS_CANCELLED
        request_obj.current_approver = None
        request_obj.current_approver_role = ""
        request_obj.save()
    return request_obj


# --- Finance / purchasing lifecycle (post-approval) ---------------------

def mark_purchase_in_progress(request_obj, actor):
    _require_finance_or_admin(actor)
    request_obj.status = Request.STATUS_PURCHASE_IN_PROGRESS
    request_obj.save()
    return request_obj


def mark_purchased(request_obj, actor):
    _require_finance_or_admin(actor)
    request_obj.status = Request.STATUS_PURCHASED
    request_obj.save()
    return request_obj


def mark_paid(request_obj, actor, *, actual_amount=None, invoice_number="", payment_date=None, notes=""):
    _require_finance_or_admin(actor)
    from .models import PaymentDetail

    PaymentDetail.objects.update_or_create(
        request=request_obj,
        defaults=dict(
            actual_amount=actual_amount,
            invoice_number=invoice_number,
            payment_date=payment_date,
            notes=notes,
            recorded_by=actor,
        ),
    )
    if actual_amount is not None:
        request_obj.actual_cost = actual_amount
    request_obj.status = Request.STATUS_PAID
    request_obj.save()
    return request_obj


def mark_completed(request_obj, actor):
    if request_obj.requester_id != actor.id and not actor.is_admin_role and not actor.is_finance:
        raise ApprovalError("მხოლოდ მომთხოვნელს, ფინანსებს ან ადმინისტრატორს შეუძლია ამ მოთხოვნის დახურვა.")
    request_obj.status = Request.STATUS_COMPLETED
    request_obj.save()
    return request_obj


def _require_finance_or_admin(actor):
    if not (actor.is_finance or actor.is_admin_role):
        raise ApprovalError("ამ მოქმედებას მხოლოდ ფინანსები ან ადმინისტრატორი ასრულებს.")
