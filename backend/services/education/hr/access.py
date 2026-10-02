"""Who may do what in the HR screens, and small helpers shared by the HR views."""
from datetime import date

from rest_framework.response import Response

from services.core.accounts.decorators import get_user_role, is_admin
from services.core.user_notifications.utils import create_user_notification, get_user_by_email
from services.education.academics.models import Teacher


def is_hr(user) -> bool:
    """Administrators plus people with the manager or HR role."""
    return bool(user and user.is_authenticated and (is_admin(user) or get_user_role(user) in ('manager', 'hr')))


def is_payroll(user) -> bool:
    """Who may see or change pay: administrators and the HR role (not every manager)."""
    return bool(user and user.is_authenticated and (is_admin(user) or get_user_role(user) == 'hr'))


def teacher_for(user):
    """The staff record that belongs to this login, if there is one."""
    email = getattr(user, 'email', '') or ''
    return Teacher.objects.filter(email__iexact=email).first() if email else None


def err(message, code=400, **extra):
    return Response({'error': message, **extra}, status=code)


def notify_teacher(teacher, title, message):
    """Tell one staff member by in-app notification (silently skipped if they have no login)."""
    if teacher is not None:
        create_user_notification(get_user_by_email(teacher.email), title, message, 'system')


def parse_date(value, what='Date'):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        raise ValueError(f'{what} must be a date like 2026-10-05.')


def whole(value, what, low, high):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'{what} must be a whole number.')
    if not low <= n <= high:
        raise ValueError(f'{what} must be between {low} and {high}.')
    return n
