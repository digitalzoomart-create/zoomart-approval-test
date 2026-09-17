def nav_context(request):
    """Small pieces of data every template needs (e.g. sidebar badge counts)."""
    if not request.user.is_authenticated:
        return {}
    from requests_app.models import RequestApproval

    pending_for_me = RequestApproval.objects.pending_for_user(request.user).count()
    return {
        "nav_pending_approvals_count": pending_for_me,
    }
