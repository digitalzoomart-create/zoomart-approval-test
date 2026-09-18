from django.contrib.auth.models import Group
from django.test import Client, TestCase

from core.models import Department
from .models import User


class TeamManagementTestCase(TestCase):
    def setUp(self):
        for name in ["Employee", "Manager", "Finance", "Administrator", "Senior Management", "Procurement Manager"]:
            Group.objects.get_or_create(name=name)
        self.dept = Department.objects.create(name="Marketing")
        self.admin = User.objects.create_user(username="admin1", password="pass12345")
        self.admin.groups.add(Group.objects.get(name="Administrator"))
        self.admin.is_staff = True
        self.admin.save()
        self.employee = User.objects.create_user(username="emp1", password="pass12345", department=self.dept)
        self.employee.groups.add(Group.objects.get(name="Employee"))

        self.client = Client()
        self.client.force_login(self.admin)

    def test_non_admin_gets_404(self):
        client = Client()
        client.force_login(self.employee)
        resp = client.get("/management/team/")
        self.assertEqual(resp.status_code, 404)

    def test_admin_can_view_team_list(self):
        resp = self.client.get("/management/team/")
        self.assertEqual(resp.status_code, 200)

    def test_creating_department_director_sets_department_manager(self):
        resp = self.client.post("/management/team/new/", {
            "first_name": "Tamar", "last_name": "Lomidze", "username": "tamar.l",
            "email": "tamar@zoomart.ge", "department": self.dept.pk, "role": "Manager",
            "password": "supersecret1",
        })
        self.assertEqual(resp.status_code, 302)
        new_user = User.objects.get(username="tamar.l")
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.manager_id, new_user.id)
        self.assertEqual(new_user.primary_role, "Manager")
        self.assertTrue(new_user.check_password("supersecret1"))

    def test_department_required_for_employee_role(self):
        resp = self.client.post("/management/team/new/", {
            "first_name": "No", "last_name": "Dept", "username": "nodept",
            "email": "", "department": "", "role": "Employee",
            "password": "supersecret1",
        })
        self.assertEqual(resp.status_code, 200)  # form re-rendered with error
        self.assertFalse(User.objects.filter(username="nodept").exists())

    def test_changing_role_away_from_manager_clears_directorship(self):
        director = User.objects.create_user(username="dir1", password="pass12345", department=self.dept)
        director.groups.add(Group.objects.get(name="Manager"))
        self.dept.manager = director
        self.dept.save()

        resp = self.client.post(f"/management/team/{director.pk}/edit/", {
            "first_name": "Dir", "last_name": "One", "username": "dir1",
            "email": "", "department": "", "role": "Finance", "password": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.dept.refresh_from_db()
        self.assertIsNone(self.dept.manager_id)
        director.refresh_from_db()
        self.assertEqual(director.primary_role, "Finance")

    def test_moving_director_to_new_department_updates_both(self):
        dept2 = Department.objects.create(name="IT")
        director = User.objects.create_user(username="dir2", password="pass12345", department=self.dept)
        director.groups.add(Group.objects.get(name="Manager"))
        self.dept.manager = director
        self.dept.save()

        resp = self.client.post(f"/management/team/{director.pk}/edit/", {
            "first_name": "Dir", "last_name": "Two", "username": "dir2",
            "email": "", "department": dept2.pk, "role": "Manager", "password": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.dept.refresh_from_db()
        dept2.refresh_from_db()
        self.assertIsNone(self.dept.manager_id)
        self.assertEqual(dept2.manager_id, director.id)

    def test_toggle_active_deactivates_and_reactivates(self):
        resp = self.client.post(f"/management/team/{self.employee.pk}/toggle-active/")
        self.assertEqual(resp.status_code, 302)
        self.employee.refresh_from_db()
        self.assertFalse(self.employee.is_active)

        resp = self.client.post(f"/management/team/{self.employee.pk}/toggle-active/")
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.is_active)

    def test_cannot_deactivate_self(self):
        resp = self.client.post(f"/management/team/{self.admin.pk}/toggle-active/")
        self.assertEqual(resp.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_editing_person_does_not_require_password(self):
        resp = self.client.post(f"/management/team/{self.employee.pk}/edit/", {
            "first_name": "Emp", "last_name": "One", "username": "emp1",
            "email": "emp1@zoomart.ge", "department": self.dept.pk, "role": "Employee", "password": "",
        })
        self.assertEqual(resp.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.email, "emp1@zoomart.ge")

    def test_department_create_and_edit(self):
        resp = self.client.post("/management/departments/new/", {"name": "Logistics", "is_active": "on"})
        self.assertEqual(resp.status_code, 302)
        new_dept = Department.objects.get(name="Logistics")

        resp = self.client.post(f"/management/departments/{new_dept.pk}/edit/", {"name": "Logistics Team"})
        self.assertEqual(resp.status_code, 302)
        new_dept.refresh_from_db()
        self.assertEqual(new_dept.name, "Logistics Team")
        self.assertFalse(new_dept.is_active, "unchecked checkbox should turn is_active off")
