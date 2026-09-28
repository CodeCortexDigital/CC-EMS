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

TEACHER_SYSTEM = (
    "You are an experienced school teacher and curriculum designer in Pakistan. "
    "Produce accurate, age-appropriate classroom material. Use plain language suited "
    "to the grade. Do not invent facts; keep content aligned with standard textbooks."
)


def generate_lesson_plan(llm: LLMClient, *, subject: str, grade: str, topic: str,
                         objectives: list[str], duration: int = 40) -> tuple[dict, Usage, str]:
    goals = "; ".join(o for o in objectives if o) or "decide suitable objectives"
    prompt = (
        f"Write a lesson plan.\n"
        f"Subject: {subject}\nClass/grade: {grade}\nTopic: {topic}\n"
        f"Learning objectives: {goals}\nPeriod length: {duration} minutes\n\n"
        "main_activities: 3-5 steps, each starting with its time in minutes (e.g. '10 min - ...'); "
        "the times plus the introduction must fit the period. differentiation: how to support "
        "weaker students and stretch stronger ones. assessment: 3-5 short questions to check understanding."
    )
    plan, usage, model = llm.structured(system=TEACHER_SYSTEM, prompt=prompt, schema=LESSON_PLAN_SCHEMA)
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
                  grade: str = "") -> tuple[dict, Usage, str]:
    prompt = (
        f"Write a {difficulty} quiz of exactly {count} questions.\n"
        f"Subject: {subject}\nTopic: {topic}\n" + (f"Class/grade: {grade}\n" if grade else "") +
        "\nMix question types, mostly mcq. Rules: mcq has exactly 4 distinct options and "
        "correct_answer is copied exactly from options; true_false has options ['True', 'False']; "
        "short_answer has options [] and a concise model answer. Each explanation says why the "
        "answer is right in one or two sentences."
    )
    quiz, usage, model = llm.structured(system=TEACHER_SYSTEM, prompt=prompt, schema=QUIZ_SCHEMA)
    questions = [q for q in (_clean_question(q) for q in quiz.get("questions", [])) if q]
    if not questions:
        raise LLMError("The model did not return any valid questions.")
    return {"title": quiz.get("title") or f"Quiz: {topic}", "questions": questions[:count]}, usage, model


REPORT_COMMENT_SCHEMA = _obj({"comment": _STR})

REPORT_WRITER_SYSTEM = (
    "You are an experienced class teacher in Pakistan writing report card comments for families. "
    "Base every claim only on the data given in the prompt — never invent grades, incidents or details "
    "not mentioned. Write 2-4 sentences, professional and warm, suitable for a printed report card. "
    "Refer to the student by name, not 'the student'."
)


def generate_report_comment(llm: LLMClient, *, student_name: str, subject_name: str | None, grade_summary: str,
                            attendance_summary: str, behaviour_summary: str, tone: str = "supportive",
                            language: str = "English") -> tuple[dict, Usage, str]:
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
    result, usage, model = llm.structured(system=REPORT_WRITER_SYSTEM, prompt=prompt, schema=REPORT_COMMENT_SCHEMA)
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

ADMISSIONS_SYSTEM = (
    "You are an admissions officer at a school in Pakistan, screening applications against the "
    "school's own stated criteria. Base every judgement only on the facts given — never invent "
    "grades, documents or family details not mentioned. Be fair and consistent: two similar "
    "applications should get similar scores. A missing required document or an unmet criterion "
    "is a concern, not automatic rejection — the final decision is always a human's."
)


def generate_admission_screening(llm: LLMClient, *, applicant_summary: str, documents_summary: str,
                                 criteria: list[str]) -> tuple[dict, Usage, str]:
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
    result, usage, model = llm.structured(system=ADMISSIONS_SYSTEM, prompt=prompt, schema=ADMISSION_SCREENING_SCHEMA)
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

MESSAGE_SUMMARY_SYSTEM = (
    "You summarise school communications for a busy parent. Base the summary only on the text "
    "given — never invent dates, names or requests not present in it. Write in plain, direct "
    "language a parent can skim in a few seconds."
)


def generate_message_summary(llm: LLMClient, *, title: str, body: str) -> tuple[dict, Usage, str]:
    prompt = (
        f"Title: {title}\n\nMessage:\n{body}\n\n"
        "summary: 1-2 sentences capturing what this is about and any action needed. "
        "key_points: short bullet list of specific facts a parent should not miss (dates, amounts, "
        "deadlines, what to do next); empty list if the message has no distinct sub-points beyond the summary."
    )
    result, usage, model = llm.structured(system=MESSAGE_SUMMARY_SYSTEM, prompt=prompt, schema=MESSAGE_SUMMARY_SCHEMA)
    summary = (result.get("summary") or "").strip()[:500]
    if not summary:
        raise LLMError("The model did not return a summary.")
    key_points = [str(p).strip()[:200] for p in (result.get("key_points") or []) if str(p).strip()][:8]
    return {"summary": summary, "key_points": key_points}, usage, model


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
