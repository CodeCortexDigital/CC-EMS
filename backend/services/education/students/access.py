"""Who may use the front desk and health office tools, and a small audit helper for sensitive reads.

Pickup, visitor and health records are sensitive, so each has its own short list of roles. Everything here is checked on
the server; hiding a menu item in the app is not a protection.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from services.core.accounts.decorators import _get_parent_student_ids, get_user_role


def role_of(user):
    return get_user_role(user)


def is_front_desk(user) -> bool:
    """Administrators and the front desk role."""
    return role_of(user) in ('admin', 'front_desk')


def is_nurse(user) -> bool:
    """Administrators and the nurse role."""
    return role_of(user) in ('admin', 'nurse')


def parent_student_ids(user):
    """The students a parent login may see (empty for anyone else)."""
    return _get_parent_student_ids(user) if role_of(user) == 'parent' else []


class FrontDeskOnly(BasePermission):
    message = 'Only the front desk and administrators can use this.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and is_front_desk(request.user))


class NurseOrParentReadOnly(BasePermission):
    """Nurse and administrators read and write; a parent can only read (their own children, filtered in the view)."""
    message = 'Health records are for the school nurse, administrators and the child\'s parents.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if is_nurse(user):
            return True
        return request.method in ('GET', 'HEAD', 'OPTIONS') and role_of(user) == 'parent'


def audit_read(request, what, student_id=None, record_id=None):
    """Write who looked at sensitive records to the audit log (best effort: never blocks the screen)."""
    try:
        from services.core.audit.models import AuditLog
        from services.core.tenants.context import get_current_tenant
        AuditLog.objects.create(
            user=request.user, school=get_current_tenant(), action='VIEW', resource_type=what,
            resource_id=record_id, new_data={'student': str(student_id)} if student_id else None,
            ip_address=request.META.get('REMOTE_ADDR') or None, user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512],
        )
    except Exception:
        pass


def audit_write(request, action, what, record_id=None, data=None):
    try:
        from services.core.audit.models import AuditLog
        from services.core.tenants.context import get_current_tenant
        AuditLog.objects.create(
            user=request.user, school=get_current_tenant(), action=action, resource_type=what, resource_id=record_id,
            new_data=data, ip_address=request.META.get('REMOTE_ADDR') or None,
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:512],
        )
    except Exception:
        pass


def deny(message):
    raise PermissionDenied(message)
