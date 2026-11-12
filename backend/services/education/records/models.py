import uuid

from django.conf import settings
from django.db import models

from services.core.tenants.mixins import TenantScopedModel


class CumulativeRecord(TenantScopedModel):
    """One pupil's cumulative record (指導要録), 様式1: the register of the pupil (学籍に関する記録).

    One record per student for the whole of their time at the school. The name, birth date and sex are the student's own record; what the
    form also asks for (furigana, the guardian's details, history before entry, what happened at entry and exit) is kept here. The
    guidance part (様式2) is kept year by year in ``CumulativeYear``.
    """
    LEVELS = [('elementary', '小学校'), ('junior_high', '中学校'), ('high', '高等学校')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField('education_students.Student', on_delete=models.CASCADE, related_name='cumulative_record')
    level = models.CharField(max_length=12, choices=LEVELS, default='elementary')
    student_furigana = models.CharField('ふりがな (児童生徒)', max_length=120, blank=True, default='')
    student_address = models.CharField('現住所 (児童生徒)', max_length=300, blank=True, default='')
    guardian_name = models.CharField('保護者 氏名', max_length=120, blank=True, default='')
    guardian_furigana = models.CharField('ふりがな (保護者)', max_length=120, blank=True, default='')
    guardian_address = models.CharField('現住所 (保護者)', max_length=300, blank=True, default='')
    previous_history = models.TextField('入学前の経歴', blank=True, default='')
    # 入学・編入学等
    entry_date = models.DateField(null=True, blank=True)
    entry_kind = models.CharField(max_length=10, choices=[('enrolled', '入学'), ('admitted', '編入学')], default='enrolled')
    entry_grade = models.PositiveSmallIntegerField(default=1, help_text='The year entered (1 for 入学; the year for 編入学)')
    # 転入学
    transfer_in_date = models.DateField(null=True, blank=True)
    transfer_in_grade = models.PositiveSmallIntegerField(null=True, blank=True)
    # 転学・退学等
    transfer_out_date = models.DateField(null=True, blank=True)
    transfer_out_note = models.CharField(max_length=300, blank=True, default='', help_text='Where to, or the reason for leaving')
    # 留学等 (high school)
    abroad_from = models.DateField(null=True, blank=True)
    abroad_to = models.DateField(null=True, blank=True)
    # 卒業, 進学先, 就職先等
    graduation_date = models.DateField(null=True, blank=True)
    next_school = models.CharField('進学先', max_length=200, blank=True, default='')
    next_work = models.CharField('就職先等', max_length=200, blank=True, default='')
    # The school as it should be printed (a snapshot, so a later change of the school's details does not rewrite an old record).
    school_name = models.CharField(max_length=200, blank=True, default='')
    school_address = models.CharField(max_length=300, blank=True, default='')
    course_name = models.CharField('課程名・学科名', max_length=120, blank=True, default='', help_text='High school only')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['student__full_name']


class CumulativeYear(TenantScopedModel):
    """One school year of a cumulative record: the class, the two seals (印) and 様式2, the record of guidance (指導に関する記録)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(CumulativeRecord, on_delete=models.CASCADE, related_name='years')
    grade = models.PositiveSmallIntegerField(help_text='The year inside the level (1 to 6, 1 to 3 or 1 to 4)')
    academic_year = models.ForeignKey('education_academics.AcademicYear', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    year_label = models.CharField('年度', max_length=40, blank=True, default='')
    class_name = models.CharField('学級', max_length=60, blank=True, default='')
    roll_number = models.CharField('整理番号', max_length=20, blank=True, default='')
    teacher_name = models.CharField('学級担任者 氏名', max_length=120, blank=True, default='')
    principal_name = models.CharField('校長 氏名', max_length=120, blank=True, default='')
    # 出欠の記録
    school_days = models.PositiveSmallIntegerField('授業日数', null=True, blank=True)
    suspended_days = models.PositiveSmallIntegerField('出席停止・忌引等の日数', null=True, blank=True)
    abroad_days = models.PositiveSmallIntegerField('留学中の授業日数', null=True, blank=True)
    absent_days = models.PositiveSmallIntegerField('欠席日数', null=True, blank=True)
    attendance_remarks = models.CharField('備考', max_length=300, blank=True, default='')
    # 様式2: ratings, narratives and marks (checked against records/forms.py when saved)
    content = models.JSONField(default=dict, blank=True)
    # The two seals (印), as a recorded approval by a person.
    teacher_confirmed_at = models.DateTimeField(null=True, blank=True)
    teacher_confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    principal_confirmed_at = models.DateTimeField(null=True, blank=True)
    principal_confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['record', 'grade']
        constraints = [models.UniqueConstraint(fields=['record', 'grade'], name='one_cumulative_year_per_grade')]

    @property
    def required_days(self):
        """出席しなければならない日数: school days less the days of suspension, bereavement and the like (and time abroad)."""
        if self.school_days is None:
            return None
        return max(0, self.school_days - (self.suspended_days or 0) - (self.abroad_days or 0))

    @property
    def present_days(self):
        """出席日数: the days to attend less the days absent."""
        required = self.required_days
        if required is None:
            return None
        return max(0, required - (self.absent_days or 0))

    @property
    def is_locked(self) -> bool:
        """A year the principal has put a seal on is no longer changed until an administrator re-opens it."""
        return self.principal_confirmed_at is not None


class TermReportLayout(TenantScopedModel):
    """A school's layout of the term report (通知表): subjects, rating scale, behaviour items and comment boxes. See ``termreport.py``."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=80)
    level = models.CharField(max_length=12, choices=CumulativeRecord.LEVELS, default='elementary')
    config = models.JSONField(default=dict)
    is_default = models.BooleanField(default=False, help_text='Used for new reports of students at this level')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['level', 'name']


class TermReport(TenantScopedModel):
    """One student's term report. The layout is copied in when the report is made, so changing the layout later does not rewrite old reports."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('education_students.Student', on_delete=models.CASCADE, related_name='term_reports')
    layout = models.ForeignKey(TermReportLayout, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports')
    layout_snapshot = models.JSONField(default=dict)
    term = models.ForeignKey('education_academics.Term', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    year_label = models.CharField(max_length=40, blank=True, default='')
    term_label = models.CharField(max_length=50, blank=True, default='')
    class_name = models.CharField(max_length=60, blank=True, default='')
    teacher_name = models.CharField(max_length=120, blank=True, default='')
    principal_name = models.CharField(max_length=120, blank=True, default='')
    school_days = models.PositiveSmallIntegerField(null=True, blank=True)
    suspended_days = models.PositiveSmallIntegerField(null=True, blank=True)
    absent_days = models.PositiveSmallIntegerField(null=True, blank=True)
    attendance_remarks = models.CharField(max_length=300, blank=True, default='')
    content = models.JSONField(default=dict, blank=True)
    finalised_at = models.DateTimeField(null=True, blank=True)
    finalised_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student__full_name']
        constraints = [models.UniqueConstraint(fields=['student', 'year_label', 'term_label'], name='uniq_term_report_per_term')]

    @property
    def is_locked(self) -> bool:
        return self.finalised_at is not None


class ChosashoIssue(TenantScopedModel):
    """A 調査書 (the junior-high report sent to a high school for admission) as it was when the principal issued it.

    The content is copied in (``snapshot``), so a later correction to the 指導要録 does not change a document already sent; a corrected one is a new issue.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(CumulativeRecord, on_delete=models.CASCADE, related_name='chosasho_issues')
    issued_to = models.CharField('提出先', max_length=200)
    note = models.CharField(max_length=300, blank=True, default='')
    snapshot = models.JSONField(default=dict)
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-issued_at']


class ExternalId(TenantScopedModel):
    """The ID another system uses for one of our students or teachers (for example a board of education's school-affairs system, or MEXT's
    Education Data Standard IDs), so data can be matched on import and export without relying on names. One ID per person per system."""
    KINDS = [('student', 'Student'), ('teacher', 'Teacher')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=KINDS)
    student = models.ForeignKey('education_students.Student', null=True, blank=True, on_delete=models.CASCADE, related_name='external_ids')
    teacher = models.ForeignKey('education_academics.Teacher', null=True, blank=True, on_delete=models.CASCADE, related_name='external_ids')
    system = models.CharField(max_length=80)
    external_id = models.CharField(max_length=60)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['system', 'external_id']
        constraints = [
            models.UniqueConstraint(fields=['tenant', 'system', 'kind', 'external_id'], name='uniq_external_id_per_system'),
            models.UniqueConstraint(fields=['student', 'system'], condition=models.Q(student__isnull=False), name='uniq_student_external_id_per_system'),
            models.UniqueConstraint(fields=['teacher', 'system'], condition=models.Q(teacher__isnull=False), name='uniq_teacher_external_id_per_system'),
        ]
