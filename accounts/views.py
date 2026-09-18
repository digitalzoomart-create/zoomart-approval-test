from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Department
from .forms import DepartmentForm, PersonForm
from .models import User


def _require_admin(user):
    if not user.is_admin_role:
        raise Http404


@login_required
def team_list(request):
    _require_admin(request.user)
    departments = (
        Department.objects.filter(is_active=True)
        .select_related("manager")
        .prefetch_related("members")
        .order_by("name")
    )
    company_wide = (
        User.objects.filter(groups__name__in=["Finance", "Senior Management", "Procurement Manager", "Administrator"])
        .distinct()
        .order_by("first_name", "last_name")
    )
    return render(
        request,
        "accounts/team_list.html",
        {
            "departments": departments,
            "company_wide": company_wide,
        },
    )


@login_required
def person_create(request):
    _require_admin(request.user)
    if request.method == "POST":
        form = PersonForm(request.POST, is_new=True)
        if form.is_valid():
            form.save()
            messages.success(request, f"{form.instance.get_full_name() or form.instance.username} დაემატა.")
            return redirect("team_list")
    else:
        form = PersonForm(is_new=True)
    return render(request, "accounts/team_form.html", {"form": form, "is_new": True})


@login_required
def person_edit(request, pk):
    _require_admin(request.user)
    obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = PersonForm(request.POST, instance=obj, is_new=False)
        if form.is_valid():
            form.save()
            messages.success(request, f"{obj.get_full_name() or obj.username} განახლდა.")
            return redirect("team_list")
    else:
        form = PersonForm(instance=obj, is_new=False)
    return render(request, "accounts/team_form.html", {"form": form, "is_new": False, "obj": obj})


@login_required
def person_toggle_active(request, pk):
    _require_admin(request.user)
    obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if obj.id == request.user.id:
            messages.error(request, "საკუთარი ანგარიშის დეაქტივაცია ვერ მოხერხდება.")
        else:
            obj.is_active = not obj.is_active
            obj.is_active_employee = obj.is_active
            obj.save(update_fields=["is_active", "is_active_employee"])
            messages.success(
                request,
                f"{obj.get_full_name() or obj.username} " + ("გააქტიურდა." if obj.is_active else "დეაქტივირდა."),
            )
    return redirect("team_list")


@login_required
def department_create(request):
    _require_admin(request.user)
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "დეპარტამენტი დაემატა.")
            return redirect("team_list")
    else:
        form = DepartmentForm()
    return render(request, "accounts/department_form.html", {"form": form, "is_new": True})


@login_required
def department_edit(request, pk):
    _require_admin(request.user)
    obj = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "დეპარტამენტი განახლდა.")
            return redirect("team_list")
    else:
        form = DepartmentForm(instance=obj)
    return render(request, "accounts/department_form.html", {"form": form, "is_new": False, "obj": obj})
