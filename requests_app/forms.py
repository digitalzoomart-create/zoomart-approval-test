from django import forms

from core.models import Department, RequestCategory
from .models import PaymentDetail, Request, RequestAttachment, RequestComment

TAILWIND_INPUT = "input"


def _style(fields):
    widgets = {}
    for name, field in fields.items():
        css = TAILWIND_INPUT
        if isinstance(field.widget, (forms.CheckboxInput,)):
            css = "h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
        field.widget.attrs.update({"class": css})
    return fields


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = [
            "title", "description", "department", "category", "request_type", "priority",
            "estimated_cost", "currency", "quantity", "vendor_name", "vendor_url", "product_url",
            "required_by_date", "business_justification",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "business_justification": forms.Textarea(attrs={"rows": 3}),
            "required_by_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = RequestCategory.objects.filter(is_active=True)
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        # Employees and department directors belong to exactly one department
        # and must never be able to file a request under a different one —
        # only company-wide roles (Admin, Senior Management, Finance,
        # Procurement Manager) get a free choice here.
        is_company_wide = (
            user is not None
            and (user.is_admin_role or user.is_senior_management or user.is_finance or user.is_procurement_manager)
        )
        if user is not None and not is_company_wide and user.department_id:
            self.initial["department"] = user.department_id
            self.fields["department"].queryset = Department.objects.filter(pk=user.department_id)
            self.fields["department"].disabled = True
        _style(self.fields)

    def clean_estimated_cost(self):
        value = self.cleaned_data["estimated_cost"]
        if value is None or value <= 0:
            raise forms.ValidationError("სავარაუდო ღირებულება უნდა იყოს ნულზე მეტი.")
        return value


class CommentForm(forms.ModelForm):
    class Meta:
        model = RequestComment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={"rows": 2, "placeholder": "დაწერეთ კომენტარი…", "class": TAILWIND_INPUT}
            )
        }
        labels = {"message": ""}


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = RequestAttachment
        fields = ["file"]
        widgets = {"file": forms.ClearableFileInput(attrs={"class": TAILWIND_INPUT})}


class ApprovalActionForm(forms.Form):
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "class": TAILWIND_INPUT, "placeholder": "კომენტარი (სავალდებულოა უარყოფისას / დამატებითი ინფოს მოთხოვნისას)"}),
    )


class PaymentForm(forms.ModelForm):
    class Meta:
        model = PaymentDetail
        fields = ["actual_amount", "invoice_number", "payment_date", "notes"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self.fields)
