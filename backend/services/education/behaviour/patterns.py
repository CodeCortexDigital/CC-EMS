"""Rule-based detection of behaviour patterns across a student's recent incidents
(docs table "AI Behaviour Pattern Detection"). Mirrors the style of the existing
attendance anomaly detector (ai-ml/attendance/anomaly_detector.py): deterministic
thresholds decide whether a pattern exists and what kind; an LLM (see
services/ai/generation.py) is only used to phrase the explanation for staff.
"""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from .models import BehaviourIncident


def detect_pattern(student, window_days: int = 30) -> dict | None:
    """None if nothing worth flagging; otherwise a dict describing the pattern."""
    today = timezone.now().date()
    since = today - timedelta(days=window_days)
    incidents = list(
        BehaviourIncident.objects.filter(student=student, kind='negative', date__gte=since)
        .select_related('category').order_by('date')
    )
    if len(incidents) < 2:
        return None

    midpoint = since + (today - since) / 2
    first_half = [i for i in incidents if i.date < midpoint]
    second_half = [i for i in incidents if i.date >= midpoint]
    high_severity = [i for i in incidents if i.severity in ('high', 'critical')]
    by_category = Counter(i.category.name for i in incidents)
    top_category, top_count = by_category.most_common(1)[0]

    escalating = len(second_half) > len(first_half) and len(second_half) >= 2
    repeated_category = top_count >= 2
    frequent = len(incidents) >= 3

    if not (high_severity or escalating or repeated_category or frequent):
        return None

    # Priority order, most urgent first — mirrors the anomaly detector's classification style.
    if high_severity:
        pattern_type = 'high_severity'
        severity = 'critical' if any(i.severity == 'critical' for i in high_severity) else 'high'
    elif escalating:
        pattern_type = 'escalating'
        severity = 'high' if len(incidents) >= 5 else 'medium'
    elif repeated_category:
        pattern_type = 'repeated_category'
        severity = 'medium'
    else:
        pattern_type = 'frequent'
        severity = 'medium' if len(incidents) >= 5 else 'low'

    return {
        'pattern_type': pattern_type,
        'severity': severity,
        'incident_count': len(incidents),
        'window_days': window_days,
        'by_category': dict(by_category),
        'top_category': top_category,
        'top_category_count': top_count,
        'first_half_count': len(first_half),
        'second_half_count': len(second_half),
        'incidents': incidents,
    }


def incident_summary_text(pattern: dict) -> str:
    """Plain-text description of the raw facts, for the LLM prompt / template fallback."""
    lines = [
        f"{pattern['incident_count']} negative incident(s) in the last {pattern['window_days']} days.",
        f"By category: " + ", ".join(f"{name} ({count})" for name, count in pattern['by_category'].items()),
    ]
    if pattern['pattern_type'] == 'escalating':
        lines.append(f"Frequency is rising: {pattern['first_half_count']} in the first half of the window vs "
                     f"{pattern['second_half_count']} in the second half.")
    for i in pattern['incidents'][-5:]:
        lines.append(f"- {i.date.isoformat()}: {i.category.name} ({i.severity}){f' — {i.description}' if i.description else ''}")
    return "\n".join(lines)
