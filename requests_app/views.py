from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from core.permissions import can_act_as_approver, can_comment, can_edit_request, can_view_request, visible_requests_qs
from . import services
from .forms import ApprovalActionForm, AttachmentForm, CommentForm, PaymentForm, RequestForm
from .models import PaymentDetail, Request, RequestApproval


@login_required
def dashboard(request):
    user = request.user
    my_requests = Request.objects.filter(requester=user)
    ctx = {
        "my_draft": my_requests.filter(status=Request.STATUS_DRAFT).count(),
        "my_pending": my_requests.filter(status__in=Request.OPEN_STATUSES).count(),
        "my_approved": my_requests.filter(
            status__in=[Request.STATUS_APPROVED, Request.STATUS_PURCHASE_IN_PROGRESS, Request.STATUS_PURCHASED, Request.STATUS_PAID, Request.STATUS_COMPLETED]
        ).count(),
        "my_rejected": my_requests.filter(status=Request.STATUS_REJECTED).count(),
        "my_recent": my_requests.order_by("-updated_at")[:6],
    }

    if user.is_manager or user.is_admin_role or user.is_senior_management:
        pending_qs = RequestApproval.objects.pending_for_user(user)
        ctx["approvals_waiting"] = pending_qs.count()
        ctx["approvals_recent"] = pending_qs.order_by("created_at")[:6]

    if user.is_finance or user.is_admin_role:
        ctx["finance_awaiting"] = Request.objects.filter(status=Request.STATUS_APPROVED).count()
        ctx["finance_in_progress"] = Request.objects.filter(status=Request.STATUS_PURCHASE_IN_PROGRESS).count()
        ctx["finance_awaiting_payment"] = Request.objects.filter(status=Request.STATUS_PURCHASED).count()
        ctx["finance_paid_this_month"] = (
            Request.objects.filter(status__in=[Request.STATUS_PAID, Request.STATUS_COMPLETED])
            .aggregate(total=Sum("actual_cost"))["total"] or 0
        )

    if user.is_senior_management or user.is_admin_role or user.is_procurement_manager or user.is_finance:
        approved_like = [Request.STATUS_APPROVED, Request.STATUS_PURCHASE_IN_PROGRESS, Request.STATUS_PURCHASED, Request.STATUS_PAID, Request.STATUS_COMPLETED]
        ctx["mgmt_total_requested"] = Request.objects.exclude(status=Request.STATUS_DRAFT).aggregate(t=Sum("estimated_cost"))["t"] or 0
        ctx["mgmt_total_approved"] = Request.objects.filter(status__in=approved_like).aggregate(t=Sum("estimated_cost"))["t"] or 0
        ctx["mgmt_total_paid"] = Request.objects.filter(status__in=[Request.STATUS_PAID, Request.STATUS_COMPLETED]).aggregate(t=Sum("actual_cost"))["t"] or 0
        ctx["mgmt_pending_amount"] = Request.objects.filter(status__in=Request.OPEN_STATUSES).aggregate(t=Sum("estimated_cost"))["t"] or 0
        ctx["mgmt_by_department"] = (
            Request.objects.exclude(status=Request.STATUS_DRAFT)
            .values("department__name").annotate(total=Sum("estimated_cost")).order_by("-total")[:8]
        )
        ctx["mgmt_by_category"] = (
            Request.objects.exclude(status=Request.STATUS_DRAFT)
            .values("category__name").annotate(total=Sum("estimated_cost")).order_by("-total")[:8]
        )
        ctx["mgmt_largest"] = Request.objects.exclude(status=Request.STATUS_DRAFT).order_by("-estimated_cost")[:5]

    return render(request, "dashboard/dashboard.html", ctx)


@login_required
def request_list(request):
    scope = request.GET.get("scope", "mine")
    user = request.user

    if scope == "approvals":
        qs = Request.objects.filter(pk__in=RequestApproval.objects.pending_for_user(user).values("request_id"))
        title = "ჩემი დამტკიცების მოლოდინში"
    elif scope == "finance":
        qs = visible_requests_qs(user).filter(
            status__in=[
                Request.STATUS_APPROVED, Request.STATUS_PURCHASE_IN_PROGRESS, Request.STATUS_PURCHASED,
                Request.STATUS_PAID, Request.STATUS_COMPLETED,
            ]
        )
        title = "ფინანსების რიგი — შესასრულებელი და შესრულებული"
    elif scope == "all" and (user.is_admin_role or user.is_senior_management or user.is_procurement_manager):
        qs = Request.objects.all()
        title = "ყველა მოთხოვნა"
    else:
        qs = Request.objects.filter(requester=user)
        title = "ჩემი მოთხოვნები"

    q = request.GET.get("q")
    status = request.GET.get("status")
    department = request.GET.get("department")
    category = request.GET.get("category")
    priority = request.GET.get("priority")

    if q:
        qs = qs.filter(
            Q(request_number__icontains=q) | Q(title__icontains=q) | Q(vendor_name__icontains=q)
        )
    if status:
        qs = qs.filter(status=status)
    if department:
        qs = qs.filter(department_id=department)
    if category:
        qs = qs.filter(category_id=category)
    if priority:
        qs = qs.filter(priority=priority)

    qs = qs.select_related("department", "category", "requester").order_by("-created_at")
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    from core.models import Department, RequestCategory

    return render(
        request,
        "requests/list.html",
        {
            "page_obj": page_obj,
            "title": title,
            "scope": scope,
            "statuses": Request.STATUS_CHOICES,
            "departments": Department.objects.filter(is_active=True),
            "categories": RequestCategory.objects.filter(is_active=True),
            "priorities": Request.PRIORITY_CHOICES,
        },
    )


@login_required
def request_create(request):
    if request.method == "POST":
        form = RequestForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.requester = request.user
            obj.save()
            messages.success(request, f"მონახაზი {obj.request_number} შეიქმნა.")
            return redirect("request_detail", pk=obj.pk)
    else:
        form = RequestForm(user=request.user)
    return render(request, "requests/form.html", {"form": form, "is_new": True})


@login_required
def request_edit(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if not can_edit_request(request.user, obj):
        raise Http404
    if request.method == "POST":
        form = RequestForm(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "მოთხოვნა განახლდა.")
            return redirect("request_detail", pk=obj.pk)
    else:
        form = RequestForm(instance=obj, user=request.user)
    return render(request, "requests/form.html", {"form": form, "is_new": False, "obj": obj})


@login_required
def request_detail(request, pk):
    obj = get_object_or_404(
        Request.objects.select_related("department", "category", "requester", "current_approver"), pk=pk
    )
    if not can_view_request(request.user, obj):
        raise Http404

    if request.method == "POST" and "post_comment" in request.POST:
        if can_comment(request.user, obj):
            cform = CommentForm(request.POST)
            if cform.is_valid():
                c = cform.save(commit=False)
                c.request = obj
                c.author = request.user
                c.save()
                messages.success(request, "კომენტარი დაემატა.")
                return redirect("request_detail", pk=obj.pk)
    else:
        cform = CommentForm()

    if request.method == "POST" and "upload_attachment" in request.POST:
        if can_view_request(request.user, obj):
            aform = AttachmentForm(request.POST, request.FILES)
            if aform.is_valid():
                att = aform.save(commit=False)
                att.request = obj
                att.uploaded_by = request.user
                att.original_filename = request.FILES["file"].name
                att.content_type = getattr(request.FILES["file"], "content_type", "")
                att.file_size = request.FILES["file"].size
                att.full_clean()
                att.save()
                messages.success(request, "ფაილი აიტვირთა.")
                return redirect("request_detail", pk=obj.pk)
            else:
                messages.error(request, "; ".join(f"{k}: {', '.join(v)}" for k, v in aform.errors.items()))
    else:
        aform = AttachmentForm()

    ctx = {
        "obj": obj,
        "cform": cform,
        "aform": aform,
        "action_form": ApprovalActionForm(),
        "comments": obj.comments.select_related("author"),
        "attachments": obj.attachments.select_related("uploaded_by"),
        "timeline": obj.approval_steps.select_related("assigned_to", "decided_by"),
        "can_edit": can_edit_request(request.user, obj),
        "can_act": can_act_as_approver(request.user, obj) and obj.status in services.STATUS_FOR_ROLE.values(),
        "can_submit": obj.requester_id == request.user.id and obj.status in (Request.STATUS_DRAFT, Request.STATUS_MORE_INFO),
        "can_cancel": obj.requester_id == request.user.id and obj.is_open,
        "is_finance_user": request.user.is_finance or request.user.is_admin_role,
        "payment_form": PaymentForm(instance=getattr(obj, "payment_detail", None)),
    }
    return render(request, "requests/detail.html", ctx)


@login_required
def request_submit(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        try:
            services.submit_request(obj, request.user)
            messages.success(request, f"{obj.request_number} გაგზავნილია დასამტკიცებლად.")
        except services.ApprovalError as e:
            messages.error(request, str(e))
    return redirect("request_detail", pk=pk)


@login_required
def request_cancel(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        try:
            services.cancel(obj, request.user)
            messages.success(request, f"{obj.request_number} გაუქმდა.")
        except services.ApprovalError as e:
            messages.error(request, str(e))
    return redirect("request_detail", pk=pk)


def _do_action(request, pk, action_label_needed, success_text, service_fn, needs_comment=False):
    obj = get_object_or_404(Request, pk=pk)
    if request.method != "POST":
        return redirect("request_detail", pk=pk)
    form = ApprovalActionForm(request.POST)
    comment = form.data.get("comment", "").strip() if form.is_valid() else ""
    if needs_comment and not comment:
        messages.error(request, f"{action_label_needed} — კომენტარი სავალდებულოა.")
        return redirect("request_detail", pk=pk)
    try:
        service_fn(obj, request.user, comment)
        messages.success(request, success_text)
    except services.ApprovalError as e:
        messages.error(request, str(e))
    return redirect("request_detail", pk=pk)


@login_required
def request_approve(request, pk):
    return _do_action(request, pk, "დამტკიცებისთვის", "მოთხოვნა დამტკიცდა.", services.approve, needs_comment=False)


@login_required
def request_reject(request, pk):
    return _do_action(request, pk, "უარსაყოფად", "მოთხოვნა უარყოფილია.", services.reject, needs_comment=True)


@login_required
def request_more_info(request, pk):
    return _do_action(request, pk, "დამატებითი ინფოს მოსათხოვად", "დამატებითი ინფორმაცია მოთხოვნილია.", services.request_more_info, needs_comment=True)


@login_required
def attachment_download(request, pk, att_id):
    obj = get_object_or_404(Request, pk=pk)
    if not can_view_request(request.user, obj):
        raise Http404
    att = get_object_or_404(obj.attachments, pk=att_id)
    return FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_filename)


@login_required
def finance_mark_purchase_in_progress(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        try:
            services.mark_purchase_in_progress(obj, request.user)
            messages.success(request, "მონიშნულია როგორც \"შესყიდვა მიმდინარეობს\".")
        except services.ApprovalError as e:
            messages.error(request, str(e))
    return redirect("request_detail", pk=pk)


@login_required
def finance_mark_purchased(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        try:
            services.mark_purchased(obj, request.user)
            messages.success(request, "მონიშნულია როგორც \"შეძენილი\".")
        except services.ApprovalError as e:
            messages.error(request, str(e))
    return redirect("request_detail", pk=pk)


@login_required
def finance_mark_paid(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        form = PaymentForm(request.POST, instance=getattr(obj, "payment_detail", None))
        if form.is_valid():
            try:
                services.mark_paid(
                    obj,
                    request.user,
                    actual_amount=form.cleaned_data["actual_amount"],
                    invoice_number=form.cleaned_data["invoice_number"],
                    payment_date=form.cleaned_data["payment_date"],
                    notes=form.cleaned_data["notes"],
                )
                messages.success(request, "მონიშნულია როგორც \"გადახდილი\".")
            except services.ApprovalError as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "გთხოვთ, შეასწოროთ გადახდის ფორმა.")
    return redirect("request_detail", pk=pk)


@login_required
def request_complete(request, pk):
    obj = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        try:
            services.mark_completed(obj, request.user)
            messages.success(request, "მონიშნულია როგორც \"დასრულებული\".")
        except services.ApprovalError as e:
            messages.error(request, str(e))
    return redirect("request_detail", pk=pk)
