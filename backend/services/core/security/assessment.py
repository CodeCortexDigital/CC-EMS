"""A self-assessment for a school's board: what the system itself can show, and what only the school can answer.

It is the school's own checklist, in the order a board usually asks. It is not an audit, a certificate or legal advice, and it says so. Each
line follows the themes of the PPC guidance on the Act on the Protection of Personal Information, the MEXT guidelines on school information
security and the MEXT guidelines on generative AI. It does not quote their clauses; the school's adviser should map it to the current texts.

Lines marked *system* are worked out from the school's own settings and data each time. Lines marked *school* are answered by an administrator
(yes, partly, no, with a note); the answer is kept with the person's name and time.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

STATUS = ('met', 'partly', 'open')
ANSWERS = {'yes': 'met', 'partly': 'partly', 'no': 'open'}
NOT_AUDIT = ('This is the school\'s own checklist. It is not an audit, a certificate or legal advice. Lines worked out by the system show what is '
             'set up here; lines the school answers are the school\'s own statements.')

# key, area, what is asked (shown to the school) for lines only the school can answer
MANUAL = [
    ('officer', 'Organisation', 'A person is named as responsible for the safe handling of personal information (安全管理責任者), and staff know who it is.'),
    ('training', 'Organisation', 'Staff who handle student information have been trained on it this school year.'),
    ('policy', 'Organisation', 'The school or its board has adopted a written policy on handling personal information and on using AI.'),
    ('contractors', 'Suppliers', 'Companies that handle student data for the school (hosting, email, AI provider) are listed, are bound by contract, and are supervised (委託先の監督).'),
    ('abroad', 'Suppliers', 'Families have been told if their information is stored or processed in another country, and in which (外国にある第三者への提供).'),
    ('incident', 'Incidents', 'There is a written procedure for a leak or loss, including who reports to the board and to the Personal Information Protection Commission, and it has been practised.'),
    ('backup', 'Continuity', 'Backups are taken and a restore has been tested.'),
    ('audit', 'Independent review', 'A third party has reviewed the school\'s information security this year (or the board has accepted this self-assessment instead).'),
]
MANUAL_KEYS = {k for k, _, _ in MANUAL}


def _item(key, area, text, status, evidence, source='system'):
    return {'key': key, 'area': area, 'text': text, 'status': status, 'evidence': evidence, 'source': source}


def _pct(a: int, b: int) -> int:
    return round(100 * a / b) if b else 0


def system_items(school) -> list[dict]:
    from services.ai.controls import controls
    from services.ai.settings_api import training_confirmation
    from services.core.audit import anchors, chain
    from services.core.audit.models import AuditChainHead, AuditLog
    from services.core.privacy import service as privacy
    from services.core.privacy.models import ConsentType, DataHandlingEntry, DocumentAcceptance
    from services.core.security import policy

    out = []
    # ---- Knowing what is held
    entries = DataHandlingEntry.objects.filter(school=school, is_active=True)
    n = entries.count()
    out.append(_item('register', 'What is held', 'A register says what personal information is held, why, for how long, who gets it and where it is stored (個人情報取扱台帳).',
                     'met' if n >= 8 else 'partly' if n else 'open', f'{n} lines in the data handling register.'))
    sensitive = entries.filter(sensitive=True).count()
    notice = privacy.current('school_privacy', school)
    newest = DataHandlingEntry.objects.filter(school=school).order_by('-reviewed_at').values_list('reviewed_at', flat=True).first()
    stale = bool(notice and newest and newest > notice.published_at)
    out.append(_item('notice', 'What is held', 'Families have been told the purposes of use (利用目的の通知・公表), and the notice matches the register.',
                     'open' if not notice else 'partly' if stale else 'met',
                     'No notice published.' if not notice else f'Version {notice.version} published {notice.published_at:%Y-%m-%d}' + ('; the register changed since.' if stale else '.')))
    if notice:
        from services.core.security.access import school_people

        ids = list(school_people(school))
        if ids:
            read = DocumentAcceptance.objects.filter(document=notice, user_id__in=ids).count()
            out.append(_item('notice_read', 'What is held', 'Most families and staff have read the current notice.',
                             'met' if _pct(read, len(ids)) >= 90 else 'partly' if read else 'open', f'{read} of {len(ids)} have read it ({_pct(read, len(ids))}%).'))
    out.append(_item('consent', 'What is held', 'Consent is asked for sensitive information (要配慮個人情報) such as health and support needs.',
                     'met' if not sensitive else 'met' if ConsentType.objects.filter(school=school, key='sensitive-info', is_active=True).exists() else 'open',
                     f'{sensitive} sensitive lines in the register.' + ('' if not sensitive else ' The consent question exists.' if ConsentType.objects.filter(school=school, key='sensitive-info', is_active=True).exists() else ' There is no consent question for them yet.')))
    # ---- Who may see it
    rules = policy.security_settings(school)
    out.append(_item('access_roles', 'Who may see it', 'People only reach what their role allows, checked on the server for every request.', 'met', 'Role checks are built in; see Roles & access.'))
    out.append(_item('admin_2fa', 'Who may see it', 'Administrators sign in with a second step.', 'met' if rules.get('admin_two_factor') else 'open',
                     'Required for administrators.' if rules.get('admin_two_factor') else 'Not required. Switch it on under Rules & retention.'))
    out.append(_item('idle', 'Who may see it', 'Shared computers sign people out after a period without activity.', 'met' if rules.get('idle_minutes') else 'partly',
                     f"After {rules['idle_minutes']} minutes." if rules.get('idle_minutes') else 'People stay signed in while the browser is open.'))
    out.append(_item('lockout', 'Who may see it', 'Repeated wrong passwords block the account for a while.', 'met', f"After {rules.get('lockout_attempts')} wrong passwords, for {rules.get('lockout_minutes')} minutes."))
    # ---- Watching use
    month = timezone.now() - timedelta(days=30)
    views = AuditLog.objects.filter(school=school, action='VIEW', timestamp__gte=month).count()
    out.append(_item('access_log', 'Watching use', 'Opening student records, exports and prints are logged with who and when, and reviewed.', 'met', f'{views} record views logged in the last 30 days.'))
    open_alerts = school.access_alerts.filter(status='open').count()
    out.append(_item('alerts', 'Watching use', 'Unusual use of records raises an alert that someone reviews, with a draft breach report ready.',
                     'met' if not open_alerts else 'partly', 'No alert waiting for review.' if not open_alerts else f'{open_alerts} alert(s) waiting for review.'))
    # ---- Keeping it intact
    name = str(school.pk)
    head = AuditChainHead.objects.filter(chain=name).first()
    check = chain.verify(name)
    out.append(_item('chain', 'Keeping it intact', 'The trail of decisions made with AI cannot be changed unnoticed.', 'met' if check['ok'] else 'open',
                     f"{head.last_seq if head else 0} records; " + ('the chain checks out.' if check['ok'] else 'the chain does NOT check out: ' + '; '.join(check['problems'][:2]))))
    if anchors.authority():
        stamped = school.chain_anchors.order_by('-seq').first()
        up = bool(stamped and head and stamped.seq == head.last_seq)
        out.append(_item('timestamp', 'Keeping it intact', 'The trail\'s newest hash is time-stamped by an outside authority, so it cannot be rewritten as a whole.',
                         'met' if up else 'partly' if stamped else 'open', 'Up to date.' if up else 'Stamped before, but newer records are not.' if stamped else 'Never time-stamped.'))
    else:
        out.append(_item('timestamp', 'Keeping it intact', 'The trail\'s newest hash is time-stamped by an outside authority, so it cannot be rewritten as a whole.', 'open',
                         'No time-stamping authority is set up on the server.'))
    from services.education.records.retention import GUIDANCE_YEARS, REGISTER_YEARS

    out.append(_item('retention', 'Keeping it intact', f'Student records are kept for the required time ({REGISTER_YEARS} years for the register, {GUIDANCE_YEARS} for guidance) and then disposed of deliberately.',
                     'met', 'Retention dates are tracked per student; disposal needs a typed confirmation. Confirm the start rule with the board.'))
    # ---- AI
    on = controls(school)
    t = training_confirmation(school)
    out.append(_item('ai_training', 'AI', 'The AI provider has confirmed in writing that what is sent is not used to train its models, and the school keeps that record.',
                     'met' if t else 'open', f"Recorded for {t.get('provider')} on {t.get('confirmed_on')}." if t else 'No confirmation recorded.'))
    out.append(_item('ai_enforced', 'AI', 'AI stops while that record is missing.', 'met' if on['require_training'] else 'open', 'Switched on.' if on['require_training'] else 'Switched off under AI assistant.'))
    out.append(_item('ai_notice', 'AI', 'Each person accepts the AI use notice before their first use.', 'met' if on['require_user_notice'] else 'open', 'Switched on.' if on['require_user_notice'] else 'Switched off under AI assistant.'))
    out.append(_item('ai_names', 'AI', 'Student names are replaced before anything is sent to the AI provider.', 'met' if on['mask_names'] else 'open', 'Switched on.' if on['mask_names'] else 'Switched off under AI assistant.'))
    out.append(_item('ai_human', 'AI', 'Everything the AI writes is a draft a person checks; anything it asks to do needs a person\'s approval.', 'met', 'Built in: the assistant can only ask, and an approver who is not the requester decides.'))
    return out


def saved_answers(school) -> dict:
    return dict(((getattr(school, 'settings_json', None) or {}).get('self_assessment') or {}))


def assessment(school) -> dict:
    answers = saved_answers(school)
    items = system_items(school)
    for key, area, text in MANUAL:
        a = answers.get(key) or {}
        status = ANSWERS.get(a.get('answer'), 'open')
        items.append({'key': key, 'area': area, 'text': text, 'source': 'school', 'status': status if a else 'open',
                      'evidence': (a.get('note') or '') if a else 'Not answered yet.', 'answer': a.get('answer', ''), 'answered_by': a.get('by', ''), 'answered_at': a.get('at')})
    count = {s: sum(1 for i in items if i['status'] == s) for s in STATUS}
    return {'items': items, 'summary': {**count, 'total': len(items)}, 'disclaimer': NOT_AUDIT, 'generated_at': timezone.now().isoformat()}


def answer(school, user, key: str, value: str, note: str):
    """Returns the saved answer, or (None, error)."""
    from services.core.tenants.context import use_tenant
    from services.core.tenants.models import School

    if key not in MANUAL_KEYS:
        return None, 'That line is worked out by the system; it cannot be answered by hand.'
    if value not in ANSWERS and value != '':
        return None, 'Answer yes, partly or no.'
    with use_tenant(None):
        fresh = School.objects.select_for_update().get(pk=school.pk)
        sj = dict(fresh.settings_json or {})
        saved = dict(sj.get('self_assessment') or {})
        if value == '':
            saved.pop(key, None)
        else:
            saved[key] = {'answer': value, 'note': (note or '').strip()[:500], 'by': getattr(user, 'email', ''), 'at': timezone.now().isoformat()}
        sj['self_assessment'] = saved
        fresh.settings_json = sj
        fresh.save(update_fields=['settings_json'])
    school.settings_json = fresh.settings_json
    return saved.get(key, {}), None
