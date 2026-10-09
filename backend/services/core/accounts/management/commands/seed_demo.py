"""Load the sample US school (Maple Grove Academy) as the demo school, and point the four demo logins at real people in it.

    python manage.py seed_sample_users --force   # admin/teacher/parent/student logins
    python manage.py seed_demo                   # loads sample-data/us-school/ through the importer (the only demo school)
    python manage.py seed_demo --reset           # clears Maple Grove first, then loads it again

The demo logins are wired in: teacher@code.com teaches maths, student@code.com is a Grade 8 student, parent@code.com has
two children. Safe to re-run: if the school already has students nothing is loaded (use --reset to start it again).
"""
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


DEMO_PASSWORDS = {
    "teacher@code.com": "Teacher@123",
    "parent@code.com": "Parent@123",
    "student@code.com": "Student@123",
}


class Command(BaseCommand):
    help = "Load the sample US school (Maple Grove Academy) and wire the demo logins to it."

    def add_arguments(self, parser):
        parser.add_argument("--pack", default="us-school", help="The sample school data pack to load (default: us-school).")
        parser.add_argument("--reset", action="store_true", help="Clear the demo school first.")

    def handle(self, *args, **opts):
        from services.core.security.defaults import refuse_on_live

        refuse_on_live('seed_demo')
        return self._seed_pack(opts["pack"], opts["reset"])


    PACKS = {"us-school": {"school": "Maple Grove Academy", "code": "MGA", "subdomain": "maple",
                           "profile": {"institute_name": "Maple Grove Academy", "name": "Maple Grove Academy",
                                       "tagline": "Small classes, big futures", "motto": "Small classes, big futures",
                                       "phone": "+1 (413) 555-0172", "website": "https://maplegrove.example",
                                       "address": "88 Maple Avenue, Springfield, MA 01103", "country": "United States",
                                       "currency": "USD", "language": "en", "region": "us", "region_chosen": True,
                                       "timezone": "America/New_York"}}}

    def _seed_pack(self, name, reset=False):
        """Load a sample pack as the demo school and point the four demo logins at real people in it."""
        from pathlib import Path

        from django.conf import settings

        from services.core.tenants.context import use_tenant
        from services.education.imports import loader

        if name not in self.PACKS:
            raise CommandError(f"Unknown pack '{name}'. Available: {', '.join(self.PACKS)}.")
        info = self.PACKS[name]
        path = Path(settings.BASE_DIR).parent / "sample-data" / name
        if not path.exists():
            raise CommandError(f"The pack folder {path} is missing.")
        M = lambda app, model: apps.get_model(app, model)  # noqa: E731
        School = M("core_tenants", "School")
        school = School.objects.filter(tenant_code=info["code"]).first() or School.objects.create(
            tenant_code=info["code"], school_id=f"DEMO-{info['code']}", name=info["school"], subdomain=info["subdomain"], is_active=True)
        school.settings_json = {**(school.settings_json or {}), **info["profile"]}
        school.save(update_fields=["settings_json"])
        self.school = school
        if reset:
            self._wipe_school(school)
        with use_tenant(school):
            if M("education_students", "Student").objects.exists():
                self.stdout.write(self.style.WARNING(f"{info['school']} already has students; nothing loaded. Use --reset to start it again."))
                return
            with transaction.atomic():      # all or nothing: a failure leaves no half-loaded school behind
                loader.load(path, school, "update", out=self.stdout.write)
                self._link_pack_logins(M, school)
            self._seed_lesson_plan(M)
            from services.education.academics.substitution import refresh_cover
            self.stdout.write(f"Cover arranged for {refresh_cover(60, today=date(2026, 10, 2))} approved leave(s).")
        self.stdout.write(self.style.SUCCESS(f"{info['school']} is ready. Log in as admin@code.com / Admin@123."))

    def _seed_lesson_plan(self, M):
        """One saved lesson plan for the demo teacher, so the Lesson Planner is not empty when a visitor opens it."""
        from datetime import timedelta

        from django.utils import timezone

        try:
            Teacher = M("education_academics", "Teacher")
            ClassSubject, Period = M("education_academics", "ClassSubject"), M("education_academics", "Period")
            Syllabus, Unit, Topic = M("education_academics", "Syllabus"), M("education_academics", "SyllabusUnit"), M("education_academics", "SyllabusTopic")
            LessonPlan, Year = M("education_academics", "LessonPlan"), M("education_academics", "AcademicYear")
            teacher = Teacher.objects.filter(email="teacher@code.com").first()
            cs = ClassSubject.objects.filter(class_ref__name="Grade 6", subject__code="MATH").first()
            period = Period.objects.order_by("period_number").first()
            year = Year.objects.filter(is_active=True).first() or Year.objects.order_by("-start_date").first()
            if not (teacher and cs and period and year):
                self.stdout.write("Lesson plan skipped (the demo school has no Grade 6 maths or no periods).")
                return
            syllabus, _ = Syllabus.objects.get_or_create(class_subject=cs, academic_year=year, version="1.0",
                                                         defaults={"title": "Grade 6 Mathematics", "created_by": "Demo"})
            unit, _ = Unit.objects.get_or_create(syllabus=syllabus, unit_number=1, defaults={"title": "Fractions", "order": 1})
            topic, _ = Topic.objects.get_or_create(unit=unit, title="Dividing fractions by fractions", defaults={
                "order": 1, "estimated_hours": 3,
                "learning_objectives": ["CCSS.MATH.CONTENT.6.NS.A.1: interpret and compute quotients of fractions"]})
            day = timezone.localdate()
            while day.weekday() > 4:
                day += timedelta(days=1)
            LessonPlan.objects.get_or_create(teacher=teacher, class_subject=cs, date=day, period=period, defaults={
                "syllabus_topic": topic,
                "objectives": ["Explain what it means to divide one fraction by another",
                               "Divide fractions using a visual model and the reciprocal rule",
                               "Solve word problems that involve dividing fractions"],
                "activities": ["Intro (5 min): how many 1/4-cup scoops are in 3/4 cup?",
                               "Model (15 min): tape diagrams and number lines for 3/4 divided by 1/8",
                               "Practice (15 min): partners work through six problems and explain each answer",
                               "Wrap-up (5 min): exit ticket with two questions"],
                "resources_needed": ["Fraction strips", "Whiteboard and markers", "Practice worksheet"],
                "homework": "Worksheet: problems 1-8, including two word problems.",
                "notes": "Standards: CCSS.MATH.CONTENT.6.NS.A.1. Support: keep fraction strips on desks. Stretch: write a word problem for 2/3 divided by 1/6.",
                "status": "planned"})
        except Exception as exc:  # the demo still loads without it
            self.stdout.write(self.style.WARNING(f"Lesson plan skipped: {exc}"))

    def _wipe_school(self, school):
        """Delete everything this one school owns (and nothing else), so a pack can be loaded again from scratch."""
        from django.db import IntegrityError
        from django.db.models import ProtectedError

        from services.core.portability.data import school_querysets

        sets = list(school_querysets(school))
        for _ in range(8):
            blocked = []
            for label, Model, qs in sets:
                try:
                    with transaction.atomic():
                        qs.delete()
                except (ProtectedError, IntegrityError):
                    blocked.append((label, Model, qs))
            if not blocked:
                break
            sets = blocked
        self.stdout.write(f"Cleared {school.name}.")

    def _link_pack_logins(self, M, school):
        """admin@code.com runs the school; teacher/parent/student logins are tied to a teacher, a family and a Grade 8 student."""
        from services.core.accounts.credentials import issue_credential

        User = get_user_model()
        Membership = M("core_tenants", "TenantMembership")
        Teacher, Student = M("education_academics", "Teacher"), M("education_students", "Student")
        for email, role in (("admin@code.com", "admin"), ("teacher@code.com", "teacher"), ("parent@code.com", "parent"), ("student@code.com", "student")):
            u = User.objects.filter(email=email).first()
            if u:
                # Make this school the one the login opens (an older demo school stays available but is no longer the default).
                Membership.objects.filter(user=u).exclude(school=school).update(is_primary=False)
                m, _ = Membership.objects.get_or_create(user=u, school=school, defaults={"role": role, "is_primary": True})
                if not m.is_primary:
                    m.is_primary = True
                    m.save(update_fields=["is_primary"])
        # The teacher login becomes the first maths teacher (so timetable, cover and HR pages have something to show).
        teacher = Teacher.objects.filter(role="Teacher", subjects__code="MATH").order_by("employee_id").first()
        login = User.objects.filter(email="teacher@code.com").first()
        if teacher and login:
            old = teacher.email
            # The login email is unique across schools: an older demo school's record that holds it is renamed.
            Teacher._base_manager.filter(email="teacher@code.com").exclude(pk=teacher.pk).update(email="former.demo.teacher@school.example")
            Teacher.objects.filter(pk=teacher.pk).update(email="teacher@code.com")
            User.objects.filter(email=old).exclude(pk=login.pk).delete()
            login.full_name = teacher.full_name
            login.save(update_fields=["full_name"])
            TeacherProfile = M("core_accounts", "TeacherProfile")
            tp, _ = TeacherProfile.objects.get_or_create(user=login, defaults={"employee_id": teacher.employee_id})
            grade6 = M("education_academics", "SchoolClass").objects.filter(name="Grade 6").first()
            if grade6:
                tp.assigned_classes.add(grade6)
        grade8 = list(Student.objects.filter(current_class__name="Grade 8").order_by("student_id"))
        stu_login = User.objects.filter(email="student@code.com").first()
        if grade8 and stu_login:
            s = grade8[0]
            Student._base_manager.filter(email="student@code.com").exclude(pk=s.pk).update(email="former.demo.student@school.example")
            Student.objects.filter(pk=s.pk).update(email="student@code.com")
            stu_login.full_name = s.full_name
            stu_login.save(update_fields=["full_name"])
        parent_login = User.objects.filter(email="parent@code.com").first()
        if parent_login:
            # A family with two children (a sibling pair if the pack has one, else the first two students).
            fam = None
            for f in Student.objects.exclude(household__isnull=True).values_list("household_id", flat=True).distinct():
                kids = list(Student.objects.filter(household_id=f))
                if len(kids) >= 2:
                    fam = kids
                    break
            kids = fam or list(Student.objects.order_by("student_id")[:2])
            ParentProfile = M("core_accounts", "ParentProfile")
            pp, _ = ParentProfile.objects.get_or_create(user=parent_login, defaults={"relationship_type": "mother"})
            pp.linked_students.add(*kids)
            parent_login.full_name = f"{kids[0].mother_name or kids[0].father_name or 'Parent'}"
            parent_login.save(update_fields=["full_name"])
        for email, password in DEMO_PASSWORDS.items():
            u = User.objects.filter(email=email).first()
            if u:
                issue_credential(u, password)
