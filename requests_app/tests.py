"""
Automated tests for the critical business rules called out in the
project spec (section 19): self-approval prevention, department
isolation, approval sequencing, rejection stopping the workflow,
amount-based routing, and audit logging.
"""

from django.contrib.auth.models import Group
from django.test import Client, TestCase

from accounts.models import User
from core.models import ApprovalStepRule, ApprovalWorkflowRule, Department, RequestCategory
from core.permissions import can_view_request
from . import services
from .models import Request, RequestApproval


class BaseWorkflowTestCase(TestCase):
    def setUp(self):
        for name in ["Employee", "Manager", "Finance", "Administrator", "Senior Management", "Procurement Manager"]:
            Group.objects.get_or_create(name=name)

        self.dept_a = Department.objects.create(name="Marketing")
        self.dept_b = Department.objects.create(name="IT")
        self.category = RequestCategory.objects.create(name="Office Supplies")

        self.manager_a = self._make_user("manager_a", ["Manager"], self.dept_a)
        self.manager_b = self._make_user("manager_b", ["Manager"], self.dept_b)
        self.finance_user = self._make_user("finance_user", ["Finance"])
        self.director = self._make_user("director", ["Senior Management"])
        self.procurement_manager = self._make_user("procurement_manager", ["Procurement Manager"])
        self.employee_a = self._make_user("employee_a", ["Employee"], self.dept_a)
        self.employee_a2 = self._make_user("employee_a2", ["Employee"], self.dept_a)
        self.employee_b = self._make_user("employee_b", ["Employee"], self.dept_b)

        self.dept_a.manager = self.manager_a
        self.dept_a.save()
        self.dept_b.manager = self.manager_b
        self.dept_b.save()

        # Small purchases: department director only.
        low = ApprovalWorkflowRule.objects.create(name="Low", min_amount=0, max_amount=500)
        ApprovalStepRule.objects.create(workflow_rule=low, order=1, approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)

        # Everything above: department director -> company director -> finance.
        standard = ApprovalWorkflowRule.objects.create(name="Standard", min_amount=500.01, max_amount=None)
        ApprovalStepRule.objects.create(workflow_rule=standard, order=1, approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=standard, order=2, approver_role=ApprovalStepRule.ROLE_SENIOR_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=standard, order=3, approver_role=ApprovalStepRule.ROLE_FINANCE)

    def _make_user(self, username, roles, department=None):
        u = User.objects.create_user(username=username, password="pass12345", department=department)
        u.groups.set(Group.objects.filter(name__in=roles))
        return u

    def _make_request(self, requester, department, amount, title="Test request"):
        return Request.objects.create(
            requester=requester, department=department, category=self.category,
            title=title, description="desc", business_justification="because", estimated_cost=amount,
        )


class ApprovalRoutingTests(BaseWorkflowTestCase):
    def test_low_amount_only_needs_manager(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_MANAGER)
        self.assertEqual(req.approval_steps.count(), 1)

        services.approve(req, self.manager_a, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED, "single-step chain should be fully approved")

    def test_mid_amount_needs_manager_then_director_then_finance(self):
        req = self._make_request(self.employee_a, self.dept_a, 1500)
        services.submit_request(req, self.employee_a)
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_MANAGER)

        services.approve(req, self.manager_a, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_SENIOR, "must advance to the company director next, not skip it")

        services.approve(req, self.director, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_FINANCE, "must reach Finance only after the company director approved")

        services.approve(req, self.finance_user, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)

    def test_high_amount_needs_all_three_steps(self):
        req = self._make_request(self.employee_a, self.dept_a, 25000)
        services.submit_request(req, self.employee_a)
        services.approve(req, self.manager_a, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_SENIOR)
        services.approve(req, self.director, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_FINANCE)
        services.approve(req, self.finance_user, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)


class SelfSubmissionSkipTests(BaseWorkflowTestCase):
    def test_department_director_submitting_own_request_skips_that_step(self):
        req = self._make_request(self.manager_a, self.dept_a, 1500)
        services.submit_request(req, self.manager_a)
        req.refresh_from_db()
        self.assertEqual(
            req.status, Request.STATUS_PENDING_SENIOR,
            "the department-director step must be bypassed automatically and go straight to the company director",
        )
        dept_step = req.approval_steps.get(approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)
        self.assertEqual(dept_step.decision, RequestApproval.DECISION_SKIPPED)

        services.approve(req, self.director, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_FINANCE)

    def test_department_director_submitting_own_small_request_auto_approves(self):
        # Only step in this tier is the department director's own — with
        # that step skipped, there is nothing left to approve.
        req = self._make_request(self.manager_a, self.dept_a, 300)
        services.submit_request(req, self.manager_a)
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)


class ProcurementManagerOversightTests(BaseWorkflowTestCase):
    def test_procurement_manager_can_view_any_request(self):
        req = self._make_request(self.employee_b, self.dept_b, 300)
        self.assertTrue(can_view_request(self.procurement_manager, req))

    def test_procurement_manager_cannot_act_as_approver(self):
        from core.permissions import can_act_as_approver

        req = self._make_request(self.employee_a, self.dept_a, 1500)
        services.submit_request(req, self.employee_a)
        self.assertFalse(can_act_as_approver(self.procurement_manager, req))


class NotificationTests(BaseWorkflowTestCase):
    def test_department_director_is_emailed_when_their_approval_is_needed(self):
        from django.core import mail

        self.manager_a.email = "manager_a@zoomart.ge"
        self.manager_a.save()
        req = self._make_request(self.employee_a, self.dept_a, 1500)
        mail.outbox = []
        services.submit_request(req, self.employee_a)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.manager_a.email, mail.outbox[0].to)

    def test_company_director_is_emailed_only_once_it_is_their_turn(self):
        from django.core import mail

        self.manager_a.email = "manager_a@zoomart.ge"
        self.manager_a.save()
        self.director.email = "director@zoomart.ge"
        self.director.save()
        req = self._make_request(self.employee_a, self.dept_a, 1500)
        services.submit_request(req, self.employee_a)
        mail.outbox = []
        services.approve(req, self.manager_a, "ok")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.director.email, mail.outbox[0].to)

    def test_finance_is_never_emailed(self):
        from django.core import mail

        self.manager_a.email = "manager_a@zoomart.ge"
        self.manager_a.save()
        self.director.email = "director@zoomart.ge"
        self.director.save()
        self.finance_user.email = "finance@zoomart.ge"
        self.finance_user.save()
        req = self._make_request(self.employee_a, self.dept_a, 1500)
        services.submit_request(req, self.employee_a)
        services.approve(req, self.manager_a, "ok")
        mail.outbox = []
        services.approve(req, self.director, "ok")
        for msg in mail.outbox:
            self.assertNotIn(self.finance_user.email, msg.to)


class SelfApprovalTests(BaseWorkflowTestCase):
    def test_requester_cannot_approve_own_request(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        with self.assertRaises(services.ApprovalError):
            services.approve(req, self.employee_a, "sneaky self-approval")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_MANAGER, "status must not change")

    def test_requester_cannot_reject_own_request(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        with self.assertRaises(services.ApprovalError):
            services.reject(req, self.employee_a, "trying to reject my own request")

    def test_department_manager_of_a_different_department_cannot_approve(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        with self.assertRaises(services.ApprovalError):
            services.approve(req, self.manager_b, "wrong department manager")


class RejectionAndInfoRequestTests(BaseWorkflowTestCase):
    def test_rejection_requires_comment(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        with self.assertRaises(services.ApprovalError):
            services.reject(req, self.manager_a, "")

    def test_rejection_stops_the_workflow_and_skips_remaining_steps(self):
        req = self._make_request(self.employee_a, self.dept_a, 1500)
        services.submit_request(req, self.employee_a)
        services.reject(req, self.manager_a, "Not needed right now.")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_REJECTED)
        remaining = req.approval_steps.filter(decision=RequestApproval.DECISION_PENDING)
        self.assertEqual(remaining.count(), 0, "no step should still be pending after a rejection")
        finance_step = req.approval_steps.get(approver_role=ApprovalStepRule.ROLE_FINANCE)
        self.assertEqual(finance_step.decision, RequestApproval.DECISION_SKIPPED)

    def test_more_info_then_resubmit_returns_to_same_step(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        services.request_more_info(req, self.manager_a, "Please attach a quotation.")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_MORE_INFO)

        services.submit_request(req, self.employee_a)
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_MANAGER)
        self.assertEqual(req.approval_steps.count(), 1, "should not create a duplicate step chain")

        services.approve(req, self.manager_a, "ok now")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)


class VisibilityAndPermissionTests(BaseWorkflowTestCase):
    def test_employee_cannot_see_another_departments_request(self):
        req = self._make_request(self.employee_b, self.dept_b, 300)
        self.assertFalse(can_view_request(self.employee_a, req))

    def test_employee_can_see_own_request(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        self.assertTrue(can_view_request(self.employee_a, req))

    def test_manager_can_see_their_own_departments_requests(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        self.assertTrue(can_view_request(self.manager_a, req))

    def test_manager_cannot_see_another_departments_requests(self):
        req = self._make_request(self.employee_b, self.dept_b, 300)
        self.assertFalse(can_view_request(self.manager_a, req))

    def test_confidential_request_hidden_from_department_manager_without_a_role_in_it(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        req.is_confidential = True
        req.save()
        self.assertFalse(can_view_request(self.manager_a, req), "confidential requests are opt-in visible only")

    def test_administrator_sees_everything(self):
        admin = self._make_user("admin_user", ["Administrator"])
        admin.is_superuser = True
        admin.save()
        req = self._make_request(self.employee_b, self.dept_b, 300)
        self.assertTrue(can_view_request(admin, req))

    def test_web_view_returns_404_for_unauthorized_department(self):
        req = self._make_request(self.employee_b, self.dept_b, 300)
        client = Client()
        client.force_login(self.employee_a)
        resp = client.get(f"/requests/{req.pk}/")
        self.assertEqual(resp.status_code, 404)


class AuditLogTests(BaseWorkflowTestCase):
    def test_creating_and_approving_a_request_writes_audit_log_entries(self):
        from auditlog.models import LogEntry

        before = LogEntry.objects.count()
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        services.approve(req, self.manager_a, "ok")
        after = LogEntry.objects.count()
        self.assertGreater(after, before, "audit log entries should be recorded for create/update actions")


class PendingForUserTests(BaseWorkflowTestCase):
    """Regression test: a future (not-yet-reached) step must not show up as
    'waiting for my approval' just because it defaults to a pending-like state."""

    def test_future_finance_step_does_not_appear_before_company_director_has_acted(self):
        req = self._make_request(self.employee_a, self.dept_a, 5000)  # needs Manager -> Senior -> Finance
        services.submit_request(req, self.employee_a)
        services.approve(req, self.manager_a, "ok")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_PENDING_SENIOR)

        finance_queue = RequestApproval.objects.pending_for_user(self.finance_user)
        self.assertNotIn(
            req.pk,
            finance_queue.values_list("request_id", flat=True),
            "the Finance step exists in the DB already but is not active yet, "
            "so it must not appear in Finance's queue while the company director is still pending",
        )

        director_queue = RequestApproval.objects.pending_for_user(self.director)
        self.assertIn(req.pk, director_queue.values_list("request_id", flat=True))


class RaceConditionTests(BaseWorkflowTestCase):
    def test_cannot_approve_the_same_step_twice(self):
        req = self._make_request(self.employee_a, self.dept_a, 300)
        services.submit_request(req, self.employee_a)
        services.approve(req, self.manager_a, "first approval")
        req.refresh_from_db()
        self.assertEqual(req.status, Request.STATUS_APPROVED)
        # A second approval attempt must fail cleanly, not double-advance the workflow.
        with self.assertRaises(services.ApprovalError):
            services.approve(req, self.manager_a, "second approval attempt")
