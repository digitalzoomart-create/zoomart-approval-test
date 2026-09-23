import datetime
import os

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from core.models import ApprovalStepRule, ApprovalWorkflowRule, Department, RequestCategory
from requests_app import services
from requests_app.models import Request

ROLES = ["Employee", "Manager", "Finance", "Administrator", "Senior Management", "Procurement Manager"]

CATEGORIES = [
    "საოფისე მასალები", "მაღაზიის მასალები", "შეფუთვა", "IT აღჭურვილობა",
    "პროგრამული უზრუნველყოფა / გამოწერა", "მარკეტინგი", "მოვლა-შენახვა", "შეკეთება",
    "ავეჯი", "ლოგისტიკა", "პროფესიული მომსახურება", "აღჭურვილობა", "სხვა",
]


class Command(BaseCommand):
    help = "Seeds roles, departments, categories, approval rules, demo users, and a few sample requests."

    def add_arguments(self, parser):
        parser.add_argument("--fresh", action="store_true", help="Wipe existing demo data first.")

    @transaction.atomic
    def handle(self, *args, **options):
        # Safety net: our Render startCommand runs this on every single boot
        # (originally so the free-tier demo always resets). Once real people
        # have real accounts, we must never again touch users/departments/
        # categories/requests here — no matter what flags are passed — or a
        # routine restart could wipe or duplicate real company data.
        #
        # We treat "any non-superuser user already exists" as proof this
        # database has been seeded/used before, and from then on this
        # command only makes sure the fixed system roles (Groups) exist and
        # otherwise does nothing. Set ALLOW_DEMO_RESEED=true as an explicit,
        # one-time override if a full demo reset is ever genuinely wanted
        # again on a non-production database.
        already_seeded = User.objects.filter(is_superuser=False).exists()
        allow_reseed = os.environ.get("ALLOW_DEMO_RESEED", "").strip().lower() == "true"

        for name in ROLES:
            Group.objects.get_or_create(name=name)

        if already_seeded and not allow_reseed:
            self.stdout.write(self.style.WARNING(
                "მონაცემები უკვე არსებობს — დემო მონაცემების ხელახლა ჩატვირთვა გამოტოვებულია "
                "(დაცვის მიზნით). განგებ სრული გადატვირთვისთვის დააყენეთ გარემოს ცვლადი "
                "ALLOW_DEMO_RESEED=true."
            ))
            return

        if options["fresh"]:
            Request.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        for i, name in enumerate(CATEGORIES):
            RequestCategory.objects.update_or_create(name=name, defaults={"sort_order": i})

        marketing, _ = Department.objects.get_or_create(name="მარკეტინგი")
        it_dept, _ = Department.objects.get_or_create(name="IT დეპარტამენტი")
        retail, _ = Department.objects.get_or_create(name="საცალო ვაჭრობის ოპერაციები")
        logistics, _ = Department.objects.get_or_create(name="ლოგისტიკა")

        def user(username, first, last, *, roles, department=None, superuser=False, password="Zoomart2026!"):
            u, created = User.objects.get_or_create(
                username=username,
                defaults=dict(first_name=first, last_name=last, email=f"{username}@zoomart.ge", department=department),
            )
            if created:
                u.set_password(password)
            u.department = department
            u.is_staff = superuser or "Administrator" in roles
            u.is_superuser = superuser
            u.save()
            u.groups.set(Group.objects.filter(name__in=roles))
            return u

        admin = user("admin", "Nino", "Admin", roles=["Administrator"], superuser=True)
        director = user("director", "Levan", "Beridze", roles=["Senior Management"])
        finance_user = user("finance", "Ana", "Kapanadze", roles=["Finance"])
        procurement_manager = user("procurement", "Eka", "Chubinidze", roles=["Procurement Manager"])
        mkt_manager = user("mkt.manager", "Tamar", "Lomidze", roles=["Manager"], department=marketing)
        it_manager = user("it.manager", "Giorgi", "Tsereteli", roles=["Manager"], department=it_dept)
        retail_manager = user("retail.manager", "Nika", "Gelashvili", roles=["Manager"], department=retail)
        logistics_manager = user("logistics.manager", "Sopo", "Maisuradze", roles=["Manager"], department=logistics)
        employee1 = user("employee1", "Mariam", "Kiknadze", roles=["Employee"], department=marketing)
        employee2 = user("employee2", "David", "Chikovani", roles=["Employee"], department=it_dept)
        employee3 = user("employee3", "Ketevan", "Japaridze", roles=["Employee"], department=retail)

        marketing.manager, it_dept.manager = mkt_manager, it_manager
        retail.manager, logistics.manager = retail_manager, logistics_manager
        marketing.save(); it_dept.save(); retail.save(); logistics.save()

        ApprovalWorkflowRule.objects.all().delete()

        # GIO: every request, at any amount, goes through the same full
        # three-step chain now — no more small-purchase shortcut. The
        # department director approves first, then the procurement manager
        # takes the request (can edit/correct it in full — vendor, pricing,
        # quantities — while it's their turn) and forwards it on, then the
        # company director gives the final approval. Once the company
        # director approves, the request is fully APPROVED — Finance does
        # not re-approve it, they just execute the purchase (see the
        # finance execution steps below and services.mark_*).
        # (If the department director is the one submitting, their own step
        # is skipped automatically — see services._build_steps.)
        all_amounts = ApprovalWorkflowRule.objects.create(
            name="ყველა მოთხოვნა — სრული დამტკიცების ჯაჭვი", min_amount=0, max_amount=None, priority=10,
        )
        ApprovalStepRule.objects.create(workflow_rule=all_amounts, order=1, approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=all_amounts, order=2, approver_role=ApprovalStepRule.ROLE_PROCUREMENT_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=all_amounts, order=3, approver_role=ApprovalStepRule.ROLE_SENIOR_MANAGER)

        cat = lambda n: RequestCategory.objects.get(name=n)
        today = datetime.date.today()

        def make(requester, dept, category, title, cost, justification, request_type="PURCHASE"):
            return Request.objects.create(
                requester=requester, department=dept, category=cat(category), title=title,
                description=title, estimated_cost=cost, business_justification=justification,
                required_by_date=today + datetime.timedelta(days=14), request_type=request_type,
            )

        r1 = make(employee1, marketing, "საოფისე მასალები", "პრინტერის ქაღალდი და კარტრიჯი", 320, "ოფისს დასჭირდა პრინტერის მასალების შევსება.")

        r2 = make(employee2, it_dept, "IT აღჭურვილობა", "2x ლეპტოპის დამტენის ჩანაცვლება", 1200, "ორი დამტენი გაფუჭდა, თანამშრომლებს ვერ მუშაობენ.")
        services.submit_request(r2, employee2)

        r3 = make(employee3, retail, "მაღაზიის მასალები", "ახალი თაროები ვაკის ფილიალისთვის", 4500, "ამჟამინდელი თაროები დაზიანებულია და კლიენტებისთვის სახიფათო.")
        services.submit_request(r3, employee3)
        services.approve(r3, retail_manager, "გამართლებულია, ვამტკიცებ.")

        # Demonstrates the full lifecycle: once the company director approves,
        # the request is APPROVED outright — Finance doesn't re-approve it,
        # they just execute (comment if needed, then purchase -> paid -> done).
        r4 = make(employee1, marketing, "მარკეტინგი", "Instagram ინფლუენსერების კამპანია — გაზაფხული", 1800, "საგაზაფხულო კამპანია ცხოველების საკვების კატეგორიის გასაძლიერებლად.")
        services.submit_request(r4, employee1)
        services.approve(r4, mkt_manager, "შეესაბამება Q2 მარკეტინგულ გეგმას.")
        services.approve(r4, procurement_manager, "შეთანხმებულია ინფლუენსერებთან ფასები, გადაცემულია დირექტორთან.")
        services.approve(r4, director, "დამტკიცებულია კომპანიის დონეზე.")
        r4.comments.create(author=finance_user, message="ბიუჯეტი ხელმისაწვდომია, ვიწყებთ შესყიდვას.")
        services.mark_purchase_in_progress(r4, finance_user)
        services.mark_purchased(r4, finance_user)
        services.mark_paid(r4, finance_user, actual_amount=1750, invoice_number="INV-2026-0041", payment_date=today, notes="გადაცემულია მარკეტინგისთვის.")
        services.mark_completed(r4, finance_user)

        r5 = make(employee2, it_dept, "პროგრამული უზრუნველყოფა / გამოწერა", "Figma-ს გუნდური გამოწერა (წლიური)", 950, "დიზაინის გუნდს სჭირდება ერთობლივი წვდომა.")
        services.submit_request(r5, employee2)
        services.request_more_info(r5, it_manager, "გთხოვთ დაადასტუროთ, რამდენი ადგილი გვჭირდება ფაქტობრივად.")

        r6 = make(employee3, retail, "აღჭურვილობა", "სამაცივრო კამერის შეკეთება — საბურთალოს ფილიალი", 15000, "მაცივარი უმართავდება, სახიფათოა გაყინული პროდუქციის დაკარგვა.")
        services.submit_request(r6, employee3)
        services.approve(r6, retail_manager, "სასწრაფოა, დაუყოვნებლივ ვამტკიცებ.")
        services.approve(r6, procurement_manager, "დამუშავებულია, გადაცემულია კომპანიის დირექტორთან დასამტკიცებლად.")
        services.reject(r6, director, "მოიტანეთ ორი კონკურენტული შეთავაზება, სანამ ამ მასშტაბის შეკეთებას დავამტკიცებთ.")

        # Demonstrates the "department director submits their own request" case:
        # the department-director step is skipped automatically and the request
        # goes straight to the company director.
        r7 = make(mkt_manager, marketing, "მარკეტინგი", "წლიური მარკეტინგული ღონისძიების სპონსორობა", 3200, "მარკეტინგის დირექტორის თავად შეტანილი მოთხოვნა — საკუთარი დეპარტამენტის დასტური საჭირო არ არის.")
        services.submit_request(r7, mkt_manager)

        # Fully approved, sitting in Finance's queue waiting to be purchased —
        # shows what an untouched "to execute" item looks like.
        r8 = make(employee2, it_dept, "IT აღჭურვილობა", "მონიტორები — 4 ცალი დიზაინის გუნდისთვის", 2400, "მიმდინარე მონიტორები მოძველებულია, ანელებს მუშაობას.")
        services.submit_request(r8, employee2)
        services.approve(r8, it_manager, "საჭირო აღჭურვილობაა.")
        services.approve(r8, procurement_manager, "შეთანხმებულია მიმწოდებელთან, გადაცემულია დირექტორთან.")
        services.approve(r8, director, "დამტკიცებულია.")

        self.stdout.write(self.style.SUCCESS("დემო მონაცემები შეიქმნა."))
        self.stdout.write("მომხმარებლები შესასვლელად (პაროლი: Zoomart2026!) :")
        for u in [admin, director, finance_user, procurement_manager, mkt_manager, it_manager, retail_manager, logistics_manager, employee1, employee2, employee3]:
            self.stdout.write(f"  {u.username:20s} roles={','.join(u.role_names) or ('superuser' if u.is_superuser else '')}")
