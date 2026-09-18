import datetime

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
        if options["fresh"]:
            Request.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        for name in ROLES:
            Group.objects.get_or_create(name=name)

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

        # Small purchases: department director's approval is enough.
        tier1 = ApprovalWorkflowRule.objects.create(name="500 ლარამდე", min_amount=0, max_amount=500, priority=10)
        ApprovalStepRule.objects.create(workflow_rule=tier1, order=1, approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)

        # Everything above that: department director -> company director -> finance.
        # (If the department director is the one submitting, their own step is
        # skipped automatically — see services._build_steps.)
        tier2 = ApprovalWorkflowRule.objects.create(name="500 ლარზე მეტი", min_amount=500.01, max_amount=None, priority=10)
        ApprovalStepRule.objects.create(workflow_rule=tier2, order=1, approver_role=ApprovalStepRule.ROLE_DEPARTMENT_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=tier2, order=2, approver_role=ApprovalStepRule.ROLE_SENIOR_MANAGER)
        ApprovalStepRule.objects.create(workflow_rule=tier2, order=3, approver_role=ApprovalStepRule.ROLE_FINANCE)

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

        r4 = make(employee1, marketing, "მარკეტინგი", "Instagram ინფლუენსერების კამპანია — გაზაფხული", 1800, "საგაზაფხულო კამპანია ცხოველების საკვების კატეგორიის გასაძლიერებლად.")
        services.submit_request(r4, employee1)
        services.approve(r4, mkt_manager, "შეესაბამება Q2 მარკეტინგულ გეგმას.")
        services.approve(r4, director, "დამტკიცებულია კომპანიის დონეზე.")
        services.approve(r4, finance_user, "ბიუჯეტი ხელმისაწვდომია.")

        r5 = make(employee2, it_dept, "პროგრამული უზრუნველყოფა / გამოწერა", "Figma-ს გუნდური გამოწერა (წლიური)", 950, "დიზაინის გუნდს სჭირდება ერთობლივი წვდომა.")
        services.submit_request(r5, employee2)
        services.request_more_info(r5, it_manager, "გთხოვთ დაადასტუროთ, რამდენი ადგილი გვჭირდება ფაქტობრივად.")

        r6 = make(employee3, retail, "აღჭურვილობა", "სამაცივრო კამერის შეკეთება — საბურთალოს ფილიალი", 15000, "მაცივარი უმართავდება, სახიფათოა გაყინული პროდუქციის დაკარგვა.")
        services.submit_request(r6, employee3)
        services.approve(r6, retail_manager, "სასწრაფოა, დაუყოვნებლივ ვამტკიცებ.")
        services.reject(r6, director, "მოიტანეთ ორი კონკურენტული შეთავაზება, სანამ ამ მასშტაბის შეკეთებას დავამტკიცებთ.")

        # Demonstrates the "department director submits their own request" case:
        # the department-director step is skipped automatically and the request
        # goes straight to the company director.
        r7 = make(mkt_manager, marketing, "მარკეტინგი", "წლიური მარკეტინგული ღონისძიების სპონსორობა", 3200, "მარკეტინგის დირექტორის თავად შეტანილი მოთხოვნა — საკუთარი დეპარტამენტის დასტური საჭირო არ არის.")
        services.submit_request(r7, mkt_manager)

        self.stdout.write(self.style.SUCCESS("დემო მონაცემები შეიქმნა."))
        self.stdout.write("მომხმარებლები შესასვლელად (პაროლი: Zoomart2026!) :")
        for u in [admin, director, finance_user, procurement_manager, mkt_manager, it_manager, retail_manager, logistics_manager, employee1, employee2, employee3]:
            self.stdout.write(f"  {u.username:20s} roles={','.join(u.role_names) or ('superuser' if u.is_superuser else '')}")
