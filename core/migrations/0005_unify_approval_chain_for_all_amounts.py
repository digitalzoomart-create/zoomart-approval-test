from django.db import migrations


def unify_approval_chain(apps, schema_editor):
    """GIO's request: drop the small-purchase shortcut entirely — every
    request, at any amount, must now go through the full three-step chain
    (department director -> procurement manager -> company director).

    This runs once, automatically, the next time the app deploys (migrate
    runs on every boot). It only touches the approval *rules*
    (configuration), never touches users, departments, categories, or any
    existing request/approval-history data.
    """
    ApprovalWorkflowRule = apps.get_model("core", "ApprovalWorkflowRule")
    ApprovalStepRule = apps.get_model("core", "ApprovalStepRule")

    # Turn off whatever amount-tiered rules existed before (e.g. the old
    # "under 500 GEL only needs the department director" shortcut) so none
    # of them can still match and produce a shorter chain. We deactivate
    # rather than delete so the change is easy to see/undo from Admin if
    # ever needed, and nothing that referenced these rows by id breaks.
    ApprovalWorkflowRule.objects.filter(is_active=True).update(is_active=False)

    rule = ApprovalWorkflowRule.objects.create(
        name="ყველა მოთხოვნა — სრული დამტკიცების ჯაჭვი",
        department=None,
        category=None,
        min_amount=0,
        max_amount=None,
        is_active=True,
        priority=1000,
    )
    ApprovalStepRule.objects.create(workflow_rule=rule, order=1, approver_role="DEPARTMENT_MANAGER")
    ApprovalStepRule.objects.create(workflow_rule=rule, order=2, approver_role="PROCUREMENT_MANAGER")
    ApprovalStepRule.objects.create(workflow_rule=rule, order=3, approver_role="SENIOR_MANAGER")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_alter_approvalsteprule_approver_role"),
    ]

    operations = [
        migrations.RunPython(unify_approval_chain, migrations.RunPython.noop),
    ]
