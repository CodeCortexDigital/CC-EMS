"""Teacher content generation (lesson plans, quizzes) with structured output."""
from __future__ import annotations

from .llm.base import LLMClient, LLMError, Usage


def _obj(properties: dict) -> dict:
    # Strict-mode schemas: every property required, no extras.
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}

LESSON_PLAN_SCHEMA = _obj({
    "duration_minutes": {"type": "integer"},
    "learning_objectives": _STR_LIST,
    "materials_needed": _STR_LIST,
    "introduction": _STR,
    "main_activities": _STR_LIST,
    "group_work": _STR,
    "differentiation": _STR,
    "assessment": _STR_LIST,
    "homework": _STR,
})

QUIZ_SCHEMA = _obj({
    "title": _STR,
    "questions": {"type": "array", "items": _obj({
        "question_type": {"type": "string", "enum": ["mcq", "true_false", "short_answer"]},
        "question_text": _STR,
        "options": _STR_LIST,
        "correct_answer": _STR,
        "explanation": _STR,
        "bloom_level": {"type": "string",
                        "enum": ["remember", "understand", "apply", "analyze", "evaluate", "create"]},
    })},
})

# How each school region is described to the model. 'pk' is the wording the app always used; a school that never chose a
# region keeps it. Other regions get their own place, spelling and standards.
REGION_VOICE = {
    'pk': ('in Pakistan', 'keep content aligned with standard textbooks'),
    'us': ('in the United States', 'align with Common Core or the state standards when the teacher names them, and use '
                                   'American spelling and U.S. grade levels (K-12)'),
    'uk': ('in the United Kingdom', 'align with the National Curriculum and use British spelling'),
    'intl': ('at an international school', 'keep content aligned with widely used international curricula'),
}


def _voice(region: str | None) -> tuple[str, str]:
    return REGION_VOICE.get((region or 'pk').lower(), REGION_VOICE['pk'])


def teacher_system(region: str | None = 'pk') -> str:
    place, align = _voice(region)
    return (f"You are an experienced school teacher and curriculum designer {place}. "
            "Produce accurate, age-appropriate classroom material. Use plain language suited "
            f"to the grade. Do not invent facts; {align}.")


TEACHER_SYSTEM = teacher_system('pk')


def generate_lesson_plan(llm: LLMClient, *, subject: str, grade: str, topic: str,
                         objectives: list[str], duration: int = 40, region: str = 'pk') -> tuple[dict, Usage, str]:
    goals = "; ".join(o for o in objectives if o) or "decide suitable objectives"
    prompt = (
        f"Write a lesson plan.\n"
        f"Subject: {subject}\nClass/grade: {grade}\nTopic: {topic}\n"
        f"Learning objectives: {goals}\nPeriod length: {duration} minutes\n\n"
        "main_activities: 3-5 steps, each starting with its time in minutes (e.g. '10 min - ...'); "
        "the times plus the introduction must fit the period. differentiation: how to support "
        "weaker students and stretch stronger ones. assessment: 3-5 short questions to check understanding."
    )
    plan, usage, model = llm.structured(system=teacher_system(region), prompt=prompt, schema=LESSON_PLAN_SCHEMA)
    plan["duration_minutes"] = max(10, min(int(plan.get("duration_minutes") or duration), 180))
    return plan, usage, model


def template_lesson_plan(*, subject: str, grade: str, topic: str, objectives: list[str],
                         duration: int = 40) -> dict:
    """Standard lesson structure used when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    intro = max(5, duration // 8)
    teach = max(10, duration * 3 // 8)
    practice = max(10, duration // 4)
    wrap = max(5, duration - intro - teach - practice)
    goals = [o for o in objectives if o] or [f"Explain the key ideas of {topic}", f"Apply {topic} to simple examples"]
    return {
        "source": "template",
        "duration_minutes": duration,
        "learning_objectives": goals,
        "materials_needed": [f"{subject} textbook ({grade})", "Whiteboard and markers", f"Worksheet on {topic}"],
        "introduction": f"Start with a quick question linking {topic} to what students already know, then share today's objectives.",
        "main_activities": [
            f"{teach} min - Explain {topic} with worked examples on the board",
            f"{practice} min - Students practise with the worksheet while the teacher checks work",
            f"{wrap} min - Review answers together and clear up mistakes",
        ],
        "group_work": f"In pairs, students solve one {topic} problem and explain their answer to the class.",
        "differentiation": "Give step-by-step hints to students who need support; set an extension question for fast finishers.",
        "assessment": [f"Explain {topic} in your own words.", f"Solve one new question on {topic}."],
        "homework": f"Complete the textbook exercise on {topic}.",
    }


def generate_quiz(llm: LLMClient, *, subject: str, topic: str, difficulty: str, count: int,
                  grade: str = "", region: str = 'pk') -> tuple[dict, Usage, str]:
    prompt = (
        f"Write a {difficulty} quiz of exactly {count} questions.\n"
        f"Subject: {subject}\nTopic: {topic}\n" + (f"Class/grade: {grade}\n" if grade else "") +
        "\nMix question types, mostly mcq. Rules: mcq has exactly 4 distinct options and "
        "correct_answer is copied exactly from options; true_false has options ['True', 'False']; "
        "short_answer has options [] and a concise model answer. Each explanation says why the "
        "answer is right in one or two sentences."
    )
    quiz, usage, model = llm.structured(system=teacher_system(region), prompt=prompt, schema=QUIZ_SCHEMA)
    questions = [q for q in (_clean_question(q) for q in quiz.get("questions", [])) if q]
    if not questions:
        raise LLMError("The model did not return any valid questions.")
    return {"title": quiz.get("title") or f"Quiz: {topic}", "questions": questions[:count]}, usage, model


REPORT_COMMENT_SCHEMA = _obj({"comment": _STR})

def report_writer_system(region: str | None = 'pk') -> str:
    place, _ = _voice(region)
    return (f"You are an experienced class teacher {place} writing report card comments for families. "
            "Base every claim only on the data given in the prompt — never invent grades, incidents or details "
            "not mentioned. Write 2-4 sentences, professional and warm, suitable for a printed report card. "
            "Refer to the student by name, not 'the student'.")


REPORT_WRITER_SYSTEM = report_writer_system('pk')


def generate_report_comment(llm: LLMClient, *, student_name: str, subject_name: str | None, grade_summary: str,
                            attendance_summary: str, behaviour_summary: str, tone: str = "supportive",
                            language: str = "English", region: str = 'pk') -> tuple[dict, Usage, str]:
    scope = f"the subject {subject_name}" if subject_name else "an overall (homeroom) report"
    prompt = (
        f"Write a report card comment about {scope} for {student_name}.\n"
        f"Tone: {tone}. Language: {language}.\n"
        f"Grades this term: {grade_summary}\n"
        f"Attendance this term: {attendance_summary}\n"
        f"Behaviour this term: {behaviour_summary}\n\n"
        "If performance and attendance are strong, be encouraging and specific about strengths. "
        "If either shows a concern, name it plainly and constructively and suggest one concrete next step. "
        "Do not repeat the raw numbers verbatim; describe them in words."
    )
    result, usage, model = llm.structured(system=report_writer_system(region), prompt=prompt, schema=REPORT_COMMENT_SCHEMA)
    comment = (result.get("comment") or "").strip()[:1000]
    if not comment:
        raise LLMError("The model did not return a comment.")
    return {"comment": comment}, usage, model


def template_report_comment(*, student_name: str, subject_name: str | None, grade_summary: str,
                            attendance_summary: str, behaviour_summary: str, tone: str = "supportive",
                            language: str = "English") -> dict:
    """Deterministic fallback comment when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    subject_bit = f" in {subject_name}" if subject_name else " overall"
    return {
        "source": "template",
        "comment": (
            f"{student_name}'s progress{subject_bit} this term: {grade_summary} "
            f"Attendance: {attendance_summary} Behaviour: {behaviour_summary} "
            "(Please review and personalise this comment before saving.)"
        ),
    }


ADMISSION_SCREENING_SCHEMA = _obj({
    "score": {"type": "integer"},
    "summary": _STR,
    "concerns": _STR_LIST,
})

def admissions_system(region: str | None = 'pk') -> str:
    place, _ = _voice(region)
    return (f"You are an admissions officer at a school {place}, screening applications against the "
            "school's own stated criteria. Base every judgement only on the facts given — never invent "
            "grades, documents or family details not mentioned. Be fair and consistent: two similar "
            "applications should get similar scores. A missing required document or an unmet criterion "
            "is a concern, not automatic rejection — the final decision is always a human's.")


ADMISSIONS_SYSTEM = admissions_system('pk')


def generate_admission_screening(llm: LLMClient, *, applicant_summary: str, documents_summary: str,
                                 criteria: list[str], region: str = 'pk') -> tuple[dict, Usage, str]:
    criteria_text = "\n".join(f"- {c}" for c in criteria) if criteria else "(the school has not listed specific criteria yet)"
    prompt = (
        f"Applicant:\n{applicant_summary}\n\n"
        f"Documents:\n{documents_summary}\n\n"
        f"School's admission criteria:\n{criteria_text}\n\n"
        "score: 0-100, how well this application matches the school's criteria and is ready for review "
        "(100 = clearly meets everything, 0 = major concerns). "
        "summary: 2-3 sentences a reviewer can read in place of re-reading the whole file. "
        "concerns: short list of specific things a human reviewer should check or follow up on "
        "(missing documents, unclear eligibility, etc.); empty list if there are none."
    )
    result, usage, model = llm.structured(system=admissions_system(region), prompt=prompt, schema=ADMISSION_SCREENING_SCHEMA)
    score = max(0, min(int(result.get("score") or 0), 100))
    summary = (result.get("summary") or "").strip()[:1000]
    if not summary:
        raise LLMError("The model did not return a screening summary.")
    concerns = [str(c).strip()[:200] for c in (result.get("concerns") or []) if str(c).strip()][:10]
    return {"score": score, "summary": summary, "concerns": concerns}, usage, model


def template_admission_screening(*, applicant_summary: str, documents_summary: str,
                                 criteria: list[str]) -> dict:
    """Deterministic fallback when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    return {
        "source": "template",
        "score": 50,
        "summary": "Automatic screening needs an AI provider to be configured; showing the raw application details instead.",
        "concerns": ["Review the applicant and document details below manually."],
    }


HOMEWORK_HINT_SCHEMA = _obj({"hint": _STR})

HOMEWORK_TUTOR_SYSTEM = (
    "You are a patient, encouraging tutor helping a school student with their own homework. "
    "Never give the final answer, a complete solution, or write the work for them. Give exactly "
    "ONE small step, hint, or guiding question that helps them figure out the next step themselves. "
    "Use simple, age-appropriate, encouraging language. If they ask you to just give the answer, "
    "kindly explain you're here to help them work it out, and give a hint instead. Base hints only "
    "on the assignment text given — never invent facts or answers not grounded in it."
)


def generate_homework_hint(llm: LLMClient, *, title: str, subject: str, instructions: str, question: str,
                           previous_hints: list[str]) -> tuple[dict, Usage, str]:
    asked = f"The student asks: {question}" if question else "The student doesn't know where to start."
    given = ("\n".join(f"{i + 1}. {h}" for i, h in enumerate(previous_hints))
             if previous_hints else "(none yet — this is the first hint)")
    prompt = (
        f"Homework: {title} ({subject})\nInstructions: {instructions}\n\n"
        f"{asked}\n\nHints already given:\n{given}\n\n"
        "Give the next hint (not already covered above), moving them one step closer to solving it "
        "themselves. 1-3 sentences."
    )
    result, usage, model = llm.structured(system=HOMEWORK_TUTOR_SYSTEM, prompt=prompt, schema=HOMEWORK_HINT_SCHEMA)
    hint = (result.get("hint") or "").strip()[:600]
    if not hint:
        raise LLMError("The model did not return a hint.")
    return {"hint": hint}, usage, model


def template_homework_hint(*, title: str, subject: str = "", instructions: str = "", question: str = "",
                           previous_hints: list[str] | None = None) -> dict:
    """Deterministic fallback when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    return {
        "source": "template",
        "hint": (
            f"Start by re-reading the instructions for \"{title}\" carefully and underline what it's "
            "actually asking for. Break it into smaller steps and try the first one yourself — ask "
            "your teacher if you get stuck. (AI hints need an AI provider to be configured.)"
        ),
    }


MESSAGE_SUMMARY_SCHEMA = _obj({"summary": _STR, "key_points": _STR_LIST})
MESSAGE_SUMMARY_REPLY_SCHEMA = _obj({"summary": _STR, "key_points": _STR_LIST, "suggested_reply": _STR})

MESSAGE_SUMMARY_SYSTEM = (
    "You summarise school communications for a busy parent. Base the summary only on the text "
    "given — never invent dates, names or requests not present in it. Write in plain, direct "
    "language a parent can skim in a few seconds."
)


def generate_message_summary(llm: LLMClient, *, title: str, body: str, want_reply: bool = False) -> tuple[dict, Usage, str]:
    """want_reply adds a draft answer for a staff member to edit and send; it is never sent for them."""
    prompt = (
        f"Title: {title}\n\nMessage:\n{body}\n\n"
        "summary: 1-2 sentences capturing what this is about and any action needed. "
        "key_points: short bullet list of specific facts a parent should not miss (dates, amounts, "
        "deadlines, what to do next); empty list if the message has no distinct sub-points beyond the summary."
    )
    if want_reply:
        prompt += (
            " suggested_reply: a short, polite draft answer to the most recent message from the family, written for a staff "
            "member to edit before sending. Do not promise outcomes, refunds, grades or exceptions, and do not state facts "
            "that are not in the conversation; where a decision is needed, say the school will come back to them."
        )
    result, usage, model = llm.structured(system=MESSAGE_SUMMARY_SYSTEM, prompt=prompt,
                                          schema=MESSAGE_SUMMARY_REPLY_SCHEMA if want_reply else MESSAGE_SUMMARY_SCHEMA)
    summary = (result.get("summary") or "").strip()[:500]
    if not summary:
        raise LLMError("The model did not return a summary.")
    key_points = [str(p).strip()[:200] for p in (result.get("key_points") or []) if str(p).strip()][:8]
    out = {"summary": summary, "key_points": key_points}
    if want_reply:
        out["suggested_reply"] = (result.get("suggested_reply") or "").strip()[:1500]
    return out, usage, model


def template_message_summary(*, title: str, body: str) -> dict:
    """Deterministic fallback when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    words = body.split()
    snippet = " ".join(words[:40]) + ("…" if len(words) > 40 else "")
    return {
        "source": "template",
        "summary": snippet or title,
        "key_points": [],
    }


BEHAVIOUR_PATTERN_SCHEMA = _obj({"summary": _STR, "recommended_actions": _STR_LIST})

BEHAVIOUR_PATTERN_SYSTEM = (
    "You help school staff understand a behaviour pattern flagged by a rule-based check on a "
    "student's incident log. Base every claim only on the facts given — never invent incidents, "
    "dates or details not mentioned. Be calm and factual, not alarmist; this is a draft for a "
    "human to review, not a judgement of the student."
)


def generate_behaviour_pattern_explanation(llm: LLMClient, *, student_name: str, pattern_type: str,
                                           severity: str, facts: str) -> tuple[dict, Usage, str]:
    prompt = (
        f"Student: {student_name}\nPattern flagged: {pattern_type} (severity: {severity})\n\nFacts:\n{facts}\n\n"
        "summary: 2-3 sentences a class teacher can read in a few seconds — what's happening and why it was flagged. "
        "recommended_actions: 2-4 short, concrete next steps (e.g. a check-in conversation, contacting the family, "
        "involving a counsellor) — practical, not generic platitudes."
    )
    result, usage, model = llm.structured(system=BEHAVIOUR_PATTERN_SYSTEM, prompt=prompt, schema=BEHAVIOUR_PATTERN_SCHEMA)
    summary = (result.get("summary") or "").strip()[:600]
    if not summary:
        raise LLMError("The model did not return a summary.")
    actions = [str(a).strip()[:200] for a in (result.get("recommended_actions") or []) if str(a).strip()][:6]
    return {"summary": summary, "recommended_actions": actions}, usage, model


def template_behaviour_pattern_explanation(*, student_name: str, pattern_type: str, severity: str,
                                           facts: str) -> dict:
    """Deterministic fallback when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    label = dict([
        ("escalating", "an escalating frequency of incidents"),
        ("repeated_category", "a repeated type of incident"),
        ("high_severity", "a high-severity incident"),
        ("frequent", "a high number of incidents"),
    ]).get(pattern_type, "a behaviour pattern")
    return {
        "source": "template",
        "summary": f"{student_name}'s recent record shows {label} ({severity} severity). Review the incident log below.",
        "recommended_actions": ["Review the recent incidents with the student's class teacher.",
                                "Consider a check-in conversation with the student.",
                                "Contact the family if this continues."],
    }


TRANSLATION_SCHEMA = _obj({"translated_text": _STR})

TRANSLATION_SYSTEM = (
    "You translate school communications for parents and students. Translate faithfully — do not "
    "summarise, shorten, add, or remove information. Keep names, dates, amounts and numbers exactly "
    "as given. Match the tone of the original (a formal notice stays formal)."
)


def generate_translation(llm: LLMClient, *, title: str, body: str, target_language: str) -> tuple[dict, Usage, str]:
    prompt = (
        f"Translate the following into {target_language}.\n\n"
        + (f"Title: {title}\n\n" if title else "")
        + f"Message:\n{body}\n\n"
        "translated_text: the full translation, ready to show in place of the original "
        "(include the translated title first if one was given)."
    )
    result, usage, model = llm.structured(system=TRANSLATION_SYSTEM, prompt=prompt, schema=TRANSLATION_SCHEMA)
    text = (result.get("translated_text") or "").strip()[:6000]
    if not text:
        raise LLMError("The model did not return a translation.")
    return {"translated_text": text}, usage, model


def template_translation(*, title: str, body: str, target_language: str) -> dict:
    """Deterministic fallback when no AI provider is configured.
    Marked with source="template" so the UI can say it isn't AI-written."""
    original = f"{title}\n\n{body}" if title else body
    return {
        "source": "template",
        "translated_text": f"{original}\n\n(Automatic translation to {target_language} needs an AI provider to be configured.)",
    }


def _clean_question(q: dict) -> dict | None:
    """Drop questions whose answer key is inconsistent."""
    kind = q.get("question_type")
    text = (q.get("question_text") or "").strip()
    answer = (q.get("correct_answer") or "").strip()
    if not text or not answer:
        return None
    options = [o.strip() for o in (q.get("options") or []) if o and o.strip()]
    if kind == "mcq":
        if len(options) != 4 or len(set(o.lower() for o in options)) != 4:
            return None
        match = next((o for o in options if o.lower() == answer.lower()), None)
        if match is None:
            return None
        answer = match
    elif kind == "true_false":
        if answer.lower() not in ("true", "false"):
            return None
        options, answer = ["True", "False"], answer.capitalize()
    elif kind == "short_answer":
        options = None
    else:
        return None
    return {
        "question_type": kind,
        "question_text": text,
        "options": options,
        "correct_answer": answer,
        "explanation": (q.get("explanation") or "").strip(),
        "bloom_level": q.get("bloom_level") or "",
    }


# ---------------------------------------------------------------------------
# Teacher assistant additions: standards in lesson plans, parent message drafts, rubrics
# ---------------------------------------------------------------------------
LESSON_PLAN_STANDARDS_SCHEMA = _obj({**LESSON_PLAN_SCHEMA["properties"], "standards_alignment": _STR_LIST})


def generate_lesson_plan_with_standards(llm: LLMClient, *, subject: str, grade: str, topic: str, objectives: list[str],
                                        standards: list[str], duration: int = 40, region: str = 'pk') -> tuple[dict, Usage, str]:
    goals = "; ".join(o for o in objectives if o) or "decide suitable objectives"
    listed = "\n".join(f"- {s}" for s in standards)
    prompt = (
        f"Write a lesson plan.\n"
        f"Subject: {subject}\nClass/grade: {grade}\nTopic: {topic}\n"
        f"Learning objectives: {goals}\nPeriod length: {duration} minutes\n"
        f"Standards the teacher wants addressed:\n{listed}\n\n"
        "main_activities: 3-5 steps, each starting with its time in minutes (e.g. '10 min - ...'); "
        "the times plus the introduction must fit the period. differentiation: how to support "
        "weaker students and stretch stronger ones. assessment: 3-5 short questions to check understanding. "
        "standards_alignment: one entry per listed standard, in the form 'CODE - which part of the lesson addresses it'. "
        "Use only the standards listed; never add or invent others."
    )
    plan, usage, model = llm.structured(system=teacher_system(region), prompt=prompt, schema=LESSON_PLAN_STANDARDS_SCHEMA)
    plan["duration_minutes"] = max(10, min(int(plan.get("duration_minutes") or duration), 180))
    plan["standards_alignment"] = [str(s).strip()[:300] for s in (plan.get("standards_alignment") or []) if str(s).strip()][:12]
    return plan, usage, model


def standards_alignment_template(standards: list[str]) -> list[str]:
    return [f"{s} - addressed in the main activities and checked in the assessment questions" for s in standards]


# Things that belong with the office, the nurse or a counsellor, not in a teacher's AI draft.
SENSITIVE_WORDS = (
    'medication', 'medicine', 'diagnos', 'adhd', 'autism', 'asthma', 'allerg', 'anxiety', 'depress', 'therapy', 'iep',
    '504', 'suspend', 'suspension', 'expel', 'detention', 'custody', 'divorce', 'abuse', 'police',
)
MESSAGE_KINDS = {
    'behavior_concern': 'a behaviour concern the teacher wants to raise calmly and constructively',
    'positive_note': 'a positive note celebrating something the student did well',
    'missed_assignments': 'missing or late assignments, with a clear way to catch up',
    'attendance_concern': 'a concern about absences or lateness, asking how the school can help',
    'custom': 'the message the teacher describes',
}
TONES = {'warm': 'warm and friendly', 'formal': 'formal and professional', 'brief': 'short and to the point'}

PARENT_MESSAGE_SCHEMA = _obj({"subject": _STR, "body": _STR})


def parent_message_warnings(details: str) -> list[str]:
    text = (details or '').lower()
    if not any(w in text for w in SENSITIVE_WORDS):
        return []
    return ['Your notes mention health, support-plan, discipline or family matters. Keep these for the office, the nurse or a '
            'counsellor, and check the wording before you send.']


def generate_parent_message(llm: LLMClient, *, kind: str, student_first_name: str, teacher_name: str, details: str, tone: str,
                            region: str = 'pk') -> tuple[dict, Usage, str]:
    system = (f"You help a teacher {_voice(region)[0]} write a message to a student's family. Use only the facts the "
              "teacher gives; never invent incidents, dates, grades or promises. Do not mention health, medical, "
              "special-education, disciplinary or family-circumstance details, and never compare the student with others. "
              "Be respectful and specific, and invite a reply. This is a draft the teacher will read and edit before sending.")
    prompt = (f"Write {MESSAGE_KINDS.get(kind, MESSAGE_KINDS['custom'])}.\nStudent first name: {student_first_name}\n"
              f"From: {teacher_name}\nTone: {TONES.get(tone, TONES['warm'])}\nTeacher's notes: {details}\n\n"
              "subject: a short, neutral subject line. body: the message, greeting and sign-off included, under 180 words.")
    out, usage, model = llm.structured(system=system, prompt=prompt, schema=PARENT_MESSAGE_SCHEMA)
    subject, body = (out.get("subject") or "").strip()[:200], (out.get("body") or "").strip()[:4000]
    if not body:
        raise LLMError("The model did not return a message.")
    return {"subject": subject or "A note about " + student_first_name, "body": body}, usage, model


def template_parent_message(*, kind: str, student_first_name: str, teacher_name: str, details: str) -> dict:
    opener = {
        'behavior_concern': f"I wanted to let you know about something I have noticed with {student_first_name} in class, so we can work on it together.",
        'positive_note': f"I wanted to share some good news about {student_first_name}.",
        'missed_assignments': f"I am writing about some assignments {student_first_name} has not yet handed in.",
        'attendance_concern': f"I am writing because {student_first_name} has been absent or late recently, and I would like to help.",
    }.get(kind, f"I am writing about {student_first_name}.")
    body = (f"Dear family,\n\n{opener}\n\n{details.strip()}\n\nPlease reply if you would like to talk about it. "
            f"Thank you for your support.\n\nKind regards,\n{teacher_name}")
    subject = f"Good news about {student_first_name}" if kind == 'positive_note' else f"A note about {student_first_name}"
    return {"source": "template", "subject": subject, "body": body}


RUBRIC_SCHEMA = _obj({"criteria": {"type": "array", "items": _obj({
    "name": _STR,
    "levels": {"type": "array", "items": _obj({"label": _STR, "description": _STR})},
})}})
DEFAULT_LEVELS = ['Exceeds', 'Meets', 'Approaching', 'Beginning']


def clean_rubric(raw, max_criteria: int = 8) -> list[dict]:
    """A rubric as a list of criteria, each with ordered levels. Drops anything malformed rather than guessing."""
    out = []
    for c in (raw if isinstance(raw, list) else [])[:max_criteria]:
        if not isinstance(c, dict) or not str(c.get('name') or '').strip():
            continue
        levels = [{'label': str(lv.get('label') or '').strip()[:40], 'description': str(lv.get('description') or '').strip()[:400]}
                  for lv in (c.get('levels') if isinstance(c.get('levels'), list) else []) if isinstance(lv, dict)]
        levels = [lv for lv in levels if lv['label']][:5]
        if len(levels) >= 2:
            out.append({'name': str(c['name']).strip()[:80], 'levels': levels})
    return out


def generate_rubric(llm: LLMClient, *, title: str, instructions: str, subject: str, grade: str, standards: list[str],
                    levels: list[str], region: str = 'pk') -> tuple[dict, Usage, str]:
    prompt = (f"Write a scoring rubric for this assignment.\nTitle: {title}\nSubject: {subject}\nClass/grade: {grade}\n"
              f"Instructions given to students: {instructions or '(none)'}\n"
              + (f"Standards: {'; '.join(standards)}\n" if standards else "")
              + f"Performance levels, best first: {', '.join(levels)}\n\n"
              "criteria: 3-5 criteria that matter for this assignment. For each criterion give every level a label (exactly as "
              "listed) and a one-sentence description of what that level looks like, in plain language a student understands.")
    out, usage, model = llm.structured(system=teacher_system(region), prompt=prompt, schema=RUBRIC_SCHEMA)
    criteria = clean_rubric(out.get("criteria"))
    if not criteria:
        raise LLMError("The model did not return a usable rubric.")
    return {"criteria": criteria}, usage, model


def template_rubric(*, title: str, levels: list[str]) -> dict:
    names = ['Understanding of the task', 'Quality of the work', 'Clarity and presentation']
    return {"source": "template", "criteria": [
        {"name": n, "levels": [{"label": lv, "description": f"Describe what {lv.lower()} looks like for this criterion."} for lv in levels]}
        for n in names]}


# ---------------------------------------------------------------------------
# Administrator analytics: a plain-language read of numbers the school already has
# ---------------------------------------------------------------------------
NARRATIVE_SCHEMA = _obj({"summary": _STR})


def narrative_system(region: str | None = 'pk') -> str:
    place, _ = _voice(region)
    return (f"You write short briefings for the head of a school {place}. You are given figures already calculated by the school's "
            "system. Describe only what the figures show: say what rose, fell or stands out. Never explain why something happened, "
            "never predict, never name or identify any person, and never add a figure that is not in the list. "
            "Plain sentences, no headings, no bullet points.")


def generate_narrative(llm: LLMClient, *, title: str, period: str, facts: list[dict], region: str = 'pk') -> tuple[dict, Usage, str]:
    lines = "\n".join(f"- {f['label']}: {f['value']}" + (f" ({f['change']})" if f.get('change') else "") for f in facts)
    prompt = (f"Report: {title}\nPeriod: {period}\nFigures:\n{lines}\n\n"
              "summary: 3 to 5 sentences for the head of school: the main picture first, then the one or two things most worth a look.")
    out, usage, model = llm.structured(system=narrative_system(region), prompt=prompt, schema=NARRATIVE_SCHEMA)
    text = (out.get("summary") or "").strip()[:1200]
    if not text:
        raise LLMError("The model did not return a summary.")
    return {"summary": text}, usage, model


def template_narrative(*, title: str, facts: list[dict]) -> dict:
    """The same figures as plain sentences, used when no AI provider is set up."""
    parts = []
    for f in facts:
        s = f"{f['label']}: {f['value']}"
        if f.get('change'):
            s += f" ({f['change']})"
        parts.append(s)
    return {"source": "template", "summary": f"{title}. " + ". ".join(parts) + "."}


# ---------------------------------------------------------------------------
# Daily brief: a short written read of the day's figures (counts only, never names)
# ---------------------------------------------------------------------------
BRIEF_SCHEMA = _obj({"summary": _STR})
BRIEF_TITLES = {"morning": "Morning brief", "evening": "Evening summary", "rollup": "Period summary"}


def brief_system(region: str | None = 'pk') -> str:
    place, _ = _voice(region)
    return (f"You write the daily briefing for the head of a school {place}. You are given counts and amounts that the school's "
            "system has already calculated, and nothing else. Describe only what those figures show. Never name or describe any "
            "person, never guess a cause, never predict, and never mention a figure that is not in the list. Put the items marked "
            "'needs attention' first. Plain sentences, no headings or bullet points.")


def generate_brief_narrative(llm: LLMClient, *, kind: str, date_label: str, facts: list[dict], region: str = 'pk') -> tuple[dict, Usage, str]:
    lines = "\n".join(f"- {f['label']}: {f['value']}" + (" [needs attention]" if f.get('attention') else "") for f in facts)
    goal = ("what to look at before the day starts" if kind == 'morning' else "how the day went and what is left for tomorrow")
    prompt = (f"{'Morning brief' if kind == 'morning' else 'Evening summary'} for {date_label}.\nFigures:\n{lines}\n\n"
              f"summary: 3 to 5 sentences on {goal}. Start with what needs attention; if nothing does, say so plainly.")
    out, usage, model = llm.structured(system=brief_system(region), prompt=prompt, schema=BRIEF_SCHEMA)
    text = (out.get("summary") or "").strip()[:1500]
    if not text:
        raise LLMError("The model did not return a summary.")
    return {"summary": text}, usage, model


def template_brief_narrative(*, kind: str, date_label: str, facts: list[dict]) -> str:
    """The same figures in plain words, used when no AI is set up or the AI is switched off."""
    head = f"{BRIEF_TITLES[kind]} for {date_label}."
    needs = [f for f in facts if f.get('attention')]
    if needs:
        body = "Needs attention: " + "; ".join(f"{f['label'].lower()}: {f['value']}" for f in needs[:6]) + "."
    else:
        body = "Nothing is flagged as needing attention."
    rate = next((f for f in facts if 'ttendance' in f['label']), None)
    tail = f" {rate['label']}: {rate['value']}." if rate else ""
    return f"{head} {body}{tail}"
