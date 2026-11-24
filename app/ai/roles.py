"""Role contracts and conservative, model-assisted intent selection."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from app.ai.base import AIProvider, AIProviderError, ChatMessage


class VeronicaRole(StrEnum):
    """Conversational behavior mode while keeping Veronica's identity."""

    FRIEND = "friend"
    TEACHER = "teacher"
    ASSISTANT = "assistant"


class TeachingSubject(StrEnum):
    """Broad learning categories supported by the initial teaching framework."""

    CODING = "coding"
    ACADEMIC = "academic"
    ENGLISH = "english"
    GENERAL = "general"


class TeachingLanguage(StrEnum):
    """Session-local language choice for Teacher responses."""

    AUTO = "auto"
    ENGLISH = "english"
    HINDI = "hindi"
    HINGLISH = "hinglish"


@dataclass(frozen=True)
class RoleDecision:
    """Validated classification of the current user turn."""

    role: VeronicaRole
    subject: TeachingSubject | None = None
    topic: str | None = None
    level: str | None = None
    quiz_mode: bool = False
    answer_attempt: bool = False
    answer_correct: bool | None = None
    request_hint: bool = False


class _RoleProvider(Protocol):
    def generate_response(self, messages: list[ChatMessage]) -> str: ...


_CLASSIFIER_PROMPT = """\
Classify the user's current conversational intent for Veronica. Return exactly
one JSON object and no other text:
{"role":"friend|teacher|assistant","subject":"coding|academic|english|general|null",
"topic":"short topic or null","level":"beginner|intermediate|advanced|null",
"quiz_mode":false,"answer_attempt":false,"answer_correct":null,
"request_hint":false}

FRIEND means casual conversation, greetings and check-ins, emotional sharing,
hobbies, daily-life anecdotes, or the user explicitly wanting to chat. Messages
such as "How are you?", "I'm bored", and casual school or college stories stay
Friend unless the user also makes a concrete task request. Do not choose
Assistant just because a tool could provide related information. Do not turn
casual conversation into a lesson or customer support.
TEACHER means the user wants to learn, study, practice, be quizzed, understand
a concept/code, or is answering a question Veronica asked in an active lesson.
This includes requests such as "teach me", "help me learn", "explain", and
"quiz me", even when they do not begin with those exact words.
ASSISTANT means a normal task or question, including use of an available tool.
Requests can combine teacher and assistant needs; choose teacher when learning
is a real part of the request. Keep teaching text-only unless the user
separately and explicitly requests a capability.

Use the recent conversation to identify an answer to Veronica's previous
teaching question. Only mark answer_attempt true when it is actually an
attempted answer; only mark answer_correct true/false when reasonably clear,
otherwise null. request_hint means the user explicitly asks for a hint or says
not to reveal the answer. Keep topic concise. If intent is ambiguous, choose
assistant. A prior role or mode is a preference, not a restriction: follow a
clear change in the user's current intent. Do not classify based solely on a
subject name appearing in a question.
"""

_EXPLICIT_ROLE_COMMANDS: tuple[tuple[VeronicaRole, re.Pattern[str]], ...] = (
    (
        VeronicaRole.TEACHER,
        re.compile(
            r"^(?:teacher\s+mode|start\s+teaching|let'?s\s+study|study\s+mode|"
            r"quiz\s+me(?:\s+on\b.*)?|english\s+practice)$",
            re.IGNORECASE,
        ),
    ),
    (
        VeronicaRole.FRIEND,
        re.compile(
            r"^(?:friend\s+mode|let'?s\s+just\s+talk|let'?s\s+chat|"
            r"normal\s+conversation|just\s+talk|don'?t\s+teach(?:\s+me)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        VeronicaRole.ASSISTANT,
        re.compile(r"^assistant\s+mode$", re.IGNORECASE),
    ),
)
_STRONG_TEACHER_INTENT = re.compile(
    r"^(?:(?:veronica)[,:\s]+)?(?:please\s+)?"
    r"(?:teach(?:\s+me)?|quiz\s+me|practice\s+with\s+me|"
    r"help\s+me\s+(?:understand|learn)|help\s+me\s+with\s+learning|"
    r"let'?s\s+study|i\s+want\s+to\s+learn|i(?:'d| would)\s+like\s+to\s+learn|"
    r"explain\b)",
    re.IGNORECASE,
)
_STRONG_FRIEND_INTENT = re.compile(
    r"(?:"
    r"let'?s\s+(?:just\s+)?(?:talk|chat)|just\s+talk|"
    r"normal\s+conversation|don'?t\s+teach(?:\s+me)?|"
    r"(?:hey|hi|hello)(?:\s+veronica)?"
    r"(?:[\s,!.?]*(?:how are you(?: doing)?|how'?s it going))?|"
    r"how\s+(?:are you(?: doing)?|was your day)|"
    r"i(?:'m| am)\s+bored|"
    r"college\s+(?:was\s+)?(?:really\s+|very\s+)?boring(?:\s+today)?|"
    r"(?:yaar\s+)?(?:aaj\s+)?college\s+(?:bahut\s+)?boring\s+(?:tha|thi)"
    r")\s*[.!?]*",
    re.IGNORECASE,
)
_LANGUAGE_CHOICE = re.compile(
    r"\b(?:(?:switch|change)\s+to|use|in|teach(?:\s+me)?\s+in)\s+"
    r"(english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto|my language)\b",
    re.IGNORECASE,
)
_LANGUAGE_MODE = re.compile(
    r"^(english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto)\s+mode[.!?]*$",
    re.IGNORECASE,
)
_LANGUAGE_BARE = re.compile(
    r"^(english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto|my language)[.!?]*$",
    re.IGNORECASE,
)
_LANGUAGE_ONLY_COMMAND = re.compile(
    r"^(?:(?:switch|change)\s+to|use)\s+"
    r"(?:english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto|my language)|"
    r"^(?:english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto)\s+mode[.!?]*$|"
    r"^(?:english|hindi\s*\+\s*english|hinglish|hin[\s-]?english|"
    r"hindi|auto|my language)[.!?]*$",
    re.IGNORECASE,
)


def _normalize_language_name(value: str) -> TeachingLanguage:
    normalized = re.sub(r"[\s-]+", "", value.casefold())
    if normalized in {"hinglish", "hinenglish", "hindi+english"}:
        return TeachingLanguage.HINGLISH
    if normalized == "mylanguage":
        return TeachingLanguage.AUTO
    return TeachingLanguage(normalized)


def teaching_language_from_message(message: str) -> TeachingLanguage | None:
    """Return an explicit teaching-language selection contained in a message."""
    text = message.strip()
    mode_match = _LANGUAGE_MODE.fullmatch(text)
    bare_match = _LANGUAGE_BARE.fullmatch(text)
    match = mode_match or bare_match or _LANGUAGE_CHOICE.search(message)
    if match is None:
        return None
    return _normalize_language_name(match.group(1))


def is_language_only_command(message: str) -> bool:
    """Whether a message changes language without starting/changing a lesson."""
    return _LANGUAGE_ONLY_COMMAND.fullmatch(message.strip()) is not None


def explicit_role_command(message: str) -> VeronicaRole | None:
    """Return a role only for a direct, unambiguous mode command."""
    text = " ".join(message.strip().split())
    for role, pattern in _EXPLICIT_ROLE_COMMANDS:
        if pattern.fullmatch(text):
            return role
    return None


def classify_role(
    provider: AIProvider | _RoleProvider,
    message: str,
    recent_messages: list[ChatMessage],
    *,
    preferred_role: VeronicaRole,
    teaching_context: str,
) -> RoleDecision:
    """Use explicit-intent guards, then the local text model for ambiguous intent."""
    command_role = explicit_role_command(message)
    if command_role is not None:
        if command_role is VeronicaRole.TEACHER:
            decision = _decision_with_inferred_topic(command_role, message)
            if message.casefold().startswith("quiz me"):
                return RoleDecision(
                    role=decision.role,
                    subject=decision.subject,
                    topic=decision.topic,
                    quiz_mode=True,
                )
            return decision
        return RoleDecision(role=command_role)
    if _STRONG_TEACHER_INTENT.search(message.strip()):
        return _decision_with_inferred_topic(VeronicaRole.TEACHER, message)
    if _STRONG_FRIEND_INTENT.fullmatch(message.strip()):
        return RoleDecision(role=VeronicaRole.FRIEND)

    classifier_messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                _CLASSIFIER_PROMPT
                + f"\nSession preference (may be overridden by current intent): "
                f"{preferred_role.value}.\n"
                + teaching_context
            ),
        },
        *recent_messages[-10:],
        {"role": "user", "content": message},
    ]
    try:
        raw = provider.generate_response(classifier_messages)
    except AIProviderError:
        return RoleDecision(role=VeronicaRole.ASSISTANT)
    if not isinstance(raw, str):
        return RoleDecision(role=VeronicaRole.ASSISTANT)
    decision = _parse_decision(raw)
    return decision or RoleDecision(role=VeronicaRole.ASSISTANT)


def _parse_decision(raw: str) -> RoleDecision | None:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    try:
        role = VeronicaRole(value.get("role"))
    except ValueError:
        return None
    subject_value = value.get("subject")
    try:
        subject = (
            None
            if subject_value is None
            else TeachingSubject(subject_value)
        )
    except ValueError:
        subject = None
    topic = value.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        topic = None
    level = value.get("level")
    if level not in {"beginner", "intermediate", "advanced"}:
        level = None
    answer_correct = value.get("answer_correct")
    if not isinstance(answer_correct, bool):
        answer_correct = None
    return RoleDecision(
        role=role,
        subject=subject,
        topic=topic.strip()[:120] if topic else None,
        level=level,
        quiz_mode=value.get("quiz_mode") is True,
        answer_attempt=value.get("answer_attempt") is True,
        answer_correct=answer_correct,
        request_hint=value.get("request_hint") is True,
    )


def _decision_with_inferred_topic(
    role: VeronicaRole,
    message: str,
) -> RoleDecision:
    """Tag the clearest initial subject/topic for explicit learning requests."""
    folded = message.casefold()
    subject: TeachingSubject | None = None
    topic: str | None = None
    if any(
        term in folded
        for term in ("grammar", "vocabulary", "speaking", "english practice")
    ):
        subject, topic = TeachingSubject.ENGLISH, "English practice"
    elif any(
        term in folded
        for term in (
            "python",
            "dsa",
            "javascript",
            "sql",
            "git",
            "html",
            "css",
            "loop",
            "recursion",
            "array",
            "data structure",
            "algorithm",
            "programming",
            "code",
        )
    ):
        subject = TeachingSubject.CODING
        for name in (
            "python",
            "dsa",
            "web development",
            "javascript",
            "sql",
            "git",
            "html",
            "css",
            "loop",
            "recursion",
            "array",
            "data structure",
            "algorithm",
        ):
            if name in folded:
                topic = name.title() if name != "dsa" else "DSA"
                break
        if topic is None:
            topic = "Programming concepts"
    elif any(term in folded for term in ("math", "bca", "computer science", "dbms")):
        subject, topic = TeachingSubject.ACADEMIC, "Academic concepts"
    return RoleDecision(role=role, subject=subject, topic=topic)


def role_instructions(role: VeronicaRole, teaching_context: str = "") -> str:
    """Return role behavior while preserving the single Veronica personality."""
    if role is VeronicaRole.FRIEND:
        return (
            "CURRENT ROLE: FRIEND. Stay Veronica: warm, natural, and attentive. "
            "Have a real conversation, respond to what the user shared, and ask "
            "a natural follow-up when it fits. Light humor is welcome when "
            "natural. Do not force a lesson, productivity advice, customer "
            "support phrasing, or 'How can I help?' into casual conversation. "
            "Do not use computer or other tools for casual conversation."
        )
    if role is VeronicaRole.TEACHER:
        return (
            "CURRENT ROLE: TEACHER. Stay the same Veronica, now helping the "
            "user learn. Explain at the current level with small examples; "
            "invite attempts, check understanding, correct mistakes kindly, "
            "and adapt difficulty. When the user attempts an answer to your "
            "question, evaluate that answer rather than restarting the lesson. "
            "If the user asks for a hint or says not to reveal the answer, give "
            "a hint and do not reveal it. Avoid dumping complete solutions "
            "when the user is practicing. Use short exercises or quizzes when "
            "appropriate, and offer a recap after a learning segment. Do not "
            "force a rigid lesson format. Teaching is text-only: do not use "
            "computer tools for teaching, examples, or research unless the "
            "user separately and explicitly asks for that capability. Keep "
            "code examples unchanged. Verify technical details and examples "
            "before explaining them. Python has two main loop constructs, "
            "for and while. A for loop iterates over an iterable such as a "
            "list, tuple, string, or range; it does not require an index. "
            "For example:\n"
            "fruits = [\"apple\", \"banana\", \"cherry\"]\n"
            "for fruit in fruits:\n"
            "    print(fruit)\n"
            "Output:\napple\nbanana\ncherry\n"
            "The variable `fruit` receives each element one by one. "
            "A natural Hinglish explanation is: 'Python mein loops ka use "
            "kisi piece of code ko repeatedly run karne ke liye hota hai.' "
            "For Python range, the start is included "
            "and the stop is excluded: range(1, 6) yields 1, 2, 3, 4, 5; "
            "range(6) yields 0, 1, 2, 3, 4, 5. Session state:\n"
            + (teaching_context or "No lesson is active yet.")
        )
    return (
        "CURRENT ROLE: ASSISTANT. Stay Veronica: answer general questions and "
        "perform only tasks supported by the available tools. Use relevant "
        "registered tools when appropriate; never claim unperformed actions."
    )
