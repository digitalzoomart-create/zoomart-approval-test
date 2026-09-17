"""
Central place for "who can see / do what" so it's never re-implemented
(and never trusted from the frontend alone) in different views.
"""


def can_view_request(user, req):
    if not user.is_authenticated:
        return False
    if user.is_admin_role or user.is_senior_management:
        return True
    if req.requester_id == user.id:
        return True
    if req.current_approver_id == user.id:
        return True
    # Anyone who was ever assigned an approval step on this request keeps visibility.
    if req.approval_steps.filter(assigned_to_id=user.id).exists():
        return True
    if req.is_confidential:
        return False
    if user.is_finance:
        return True
    if user.is_manager and user.department_id == req.department_id:
        return True
    return False


def can_edit_request(user, req):
    if not req.is_editable:
        return False
    return req.requester_id == user.id or user.is_admin_role


def can_comment(user, req):
    return can_view_request(user, req)


def can_act_as_approver(user, req):
    """Loose check used only to decide whether to SHOW approve/reject buttons;
    the real enforcement happens server-side inside services.py."""
    if not user.is_authenticated or req.requester_id == user.id:
        return False
    if user.is_admin_role:
        return True
    if req.current_approver_id == user.id:
        return True
    if req.current_approver_id is None and req.current_approver_role in ("FINANCE",) and user.is_finance:
        return True
    if req.current_approver_id is None and req.current_approver_role in ("SENIOR_MANAGER",) and user.is_senior_management:
        return True
    return False


def visible_requests_qs(user):
    from requests_app.models import Request

    if user.is_admin_role or user.is_senior_management:
        return Request.objects.all()

    from django.db.models import Q

    q = Q(requester_id=user.id) | Q(current_approver_id=user.id) | Q(approval_steps__assigned_to_id=user.id)
    if user.is_finance:
        q |= Q(is_confidential=False)
    if user.is_manager and user.department_id:
        q |= Q(is_confidential=False, department_id=user.department_id)
    return Request.objects.filter(q).distinct()
