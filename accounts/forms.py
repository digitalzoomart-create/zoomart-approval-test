from django import forms
from django.contrib.auth.models import Group

from core.models import Department
from core.templatetags.ka_labels import ROLE_LABELS_KA
from .models import User

TAILWIND_INPUT = "input"

# Fixed, sensible order for the role dropdown (ROLE_LABELS_KA is a plain dict).
ROLE_ORDER = ["Employee", "Manager", "Finance", "Senior Management", "Procurement Manager", "Administrator"]
ROLE_CHOICES = [(key, ROLE_LABELS_KA[key]) for key in ROLE_ORDER]

# Roles that only make sense tied to one department.
DEPARTMENT_REQUIRED_ROLES = {"Employee", "Manager"}


class PersonForm(forms.ModelForm):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        label="როლი",
        help_text="განსაზღვრავს, რისი გაკეთება შეუძლია ამ ადამიანს სისტემაში.",
    )
    password = forms.CharField(
        label="პაროლი",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "username", "email", "department"]
        labels = {
            "first_name": "სახელი",
            "last_name": "გვარი",
            "username": "მომხმარებლის სახელი",
            "email": "ელფოსტა",
            "department": "დეპარტამენტი",
        }

    def __init__(self, *args, is_new=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_new = is_new
        self.fields["department"].queryset = Department.objects.filter(is_active=True)
        self.fields["department"].required = False
        self.fields["department"].empty_label = "— არცერთი (კომპანიის მასშტაბის როლისთვის) —"
        if is_new:
            self.fields["password"].required = True
            self.fields["password"].help_text = "მინიმუმ 8 სიმბოლო — გადასცით ამ ადამიანს პირველი შესვლისთვის."
        else:
            self.fields["password"].help_text = "შეავსეთ მხოლოდ თუ გსურთ პაროლის შეცვლა — სხვა შემთხვევაში დატოვეთ ცარიელი."
            self.fields["username"].disabled = True
        if self.instance.pk:
            current_role = self.instance.role_names[0] if self.instance.role_names else "Employee"
            self.fields["role"].initial = current_role
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue
            field.widget.attrs.setdefault("class", TAILWIND_INPUT)

    def clean_password(self):
        pw = self.cleaned_data.get("password", "")
        if pw and len(pw) < 8:
            raise forms.ValidationError("პაროლი უნდა შეიცავდეს მინიმუმ 8 სიმბოლოს.")
        return pw

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        department = cleaned.get("department")
        if role in DEPARTMENT_REQUIRED_ROLES and not department:
            self.add_error("department", "ამ როლისთვის დეპარტამენტის მითითება სავალდებულოა.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data["role"]
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        user.is_staff = role == "Administrator"
        if commit:
            user.save()
            group = Group.objects.get(name=role)
            user.groups.set([group])
            # Whatever department this person used to direct, they no longer do
            # (role or department may have changed) — then re-assign if it applies.
            Department.objects.filter(manager=user).update(manager=None)
            if role == "Manager" and user.department_id:
                user.department.manager = user
                user.department.save(update_fields=["manager"])
        return user


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "is_active"]
        labels = {"name": "დეპარტამენტის დასახელება", "is_active": "აქტიური"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.setdefault("class", TAILWIND_INPUT)
        self.fields["is_active"].widget.attrs.setdefault(
            "class", "h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
        )
