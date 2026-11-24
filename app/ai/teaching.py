"""Session-local state for Veronica's teacher role."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.ai.roles import (
    RoleDecision,
    TeachingLanguage,
    TeachingSubject,
    VeronicaRole,
)

_LEVELS = ("beginner", "intermediate", "advanced")


@dataclass
class TeachingSession:
    """Small, in-memory teaching state; no persistence is performed."""

    active: bool = False
    language_preference: TeachingLanguage = TeachingLanguage.AUTO
    subject: TeachingSubject | None = None
    topic: str | None = None
    level: str = "beginner"
    current_concept: str | None = None
    current_question: str | None = None
    attempts: int = 0
    difficulty: str = "beginner"
    teaching_style: str = "guided"
    quiz_mode: bool = False
    questions_answered: int = 0
    correct_answers: int = 0
    started_at: datetime | None = None
    last_turn_was_answer_attempt: bool = False
    last_turn_answer_correct: bool | None = None
    _consecutive_correct: int = field(default=0, repr=False)
    _consecutive_incorrect: int = field(default=0, repr=False)
    _hint_requested: bool = field(default=False, repr=False)

    def apply_decision(
        self,
        decision: RoleDecision,
        *,
        role: VeronicaRole,
    ) -> None:
        """Update state from the current model-classified user turn."""
        if role is not VeronicaRole.TEACHER:
            self.active = False
            self.last_turn_was_answer_attempt = False
            self.last_turn_answer_correct = None
            self._hint_requested = False
            return

        self.last_turn_was_answer_attempt = decision.answer_attempt
        self.last_turn_answer_correct = (
            decision.answer_correct if decision.answer_attempt else None
        )
        if not self.active or self.started_at is None:
            self.started_at = datetime.now().astimezone()
        self.active = True
        if decision.subject is not None:
            self.subject = decision.subject
        if decision.topic is not None:
            self.topic = decision.topic
            self.current_concept = decision.topic
        if decision.level is not None:
            self.level = decision.level
            self.difficulty = decision.level
        self.quiz_mode = decision.quiz_mode or self.quiz_mode
        self._hint_requested = decision.request_hint
        if decision.answer_attempt:
            self.record_answer(decision.answer_correct)
        elif decision.request_hint:
            self.teaching_style = "hint-first"
        elif decision.quiz_mode:
            self.teaching_style = "quiz"
        else:
            self.teaching_style = "guided"

    def record_answer(self, correct: bool | None) -> None:
        """Track an attempted answer and adjust difficulty conservatively."""
        self.attempts += 1
        self.questions_answered += 1
        if correct is True:
            self.correct_answers += 1
            self._consecutive_correct += 1
            self._consecutive_incorrect = 0
            if self._consecutive_correct >= 3:
                self._adjust_difficulty(1)
                self._consecutive_correct = 0
        elif correct is False:
            self._consecutive_incorrect += 1
            self._consecutive_correct = 0
            if self._consecutive_incorrect >= 2:
                self._adjust_difficulty(-1)
                self._consecutive_incorrect = 0
        self.current_question = None

    def set_language_preference(self, preference: TeachingLanguage) -> None:
        """Change only the session language; leave lesson progress untouched."""
        self.language_preference = preference

    def record_assistant_response(self, response: str) -> None:
        """Remember the next question asked, without retaining lesson content."""
        questions = [
            part.strip()
            for part in re.findall(r"[^?]*\?", response, flags=re.DOTALL)
            if part.strip()
        ]
        if questions and self.active:
            self.current_question = questions[-1][-300:]
        self._hint_requested = False

    def request_reset(self) -> None:
        """Clear the current learning segment while preserving a new session."""
        self.active = False
        self.language_preference = TeachingLanguage.AUTO
        self.subject = None
        self.topic = None
        self.level = "beginner"
        self.current_concept = None
        self.current_question = None
        self.attempts = 0
        self.difficulty = "beginner"
        self.teaching_style = "guided"
        self.quiz_mode = False
        self.questions_answered = 0
        self.correct_answers = 0
        self.started_at = None
        self.last_turn_was_answer_attempt = False
        self.last_turn_answer_correct = None
        self._consecutive_correct = 0
        self._consecutive_incorrect = 0
        self._hint_requested = False

    def prompt_context(self) -> str:
        """Format only concise teaching state for a teacher-role system prompt."""
        if not self.active:
            return "No lesson is active. Establish the user's learning goal naturally."
        language_guidance = {
            TeachingLanguage.AUTO: (
                "AUTO language: follow the user's language and style in each "
                "turn (English, Hindi, or natural Latin-script Hinglish). "
                "Do not switch languages without a reason."
            ),
            TeachingLanguage.ENGLISH: (
                "ENGLISH language: write every teaching explanation, example, "
                "question, hint, quiz, evaluation, correction, recap, and "
                "next-step suggestion in English."
            ),
            TeachingLanguage.HINDI: (
                "HINDI language: write every teaching explanation, example, "
                "question, hint, quiz, evaluation, correction, recap, and "
                "next-step suggestion primarily in Hindi. Technical terms and code may "
                "remain in English where appropriate."
            ),
            TeachingLanguage.HINGLISH: (
                "HINGLISH language: use natural, student-friendly, Latin-script "
                "Hinglish throughout every explanation, example, question, "
                "hint, quiz, evaluation, correction, recap, and next-step "
                "suggestion. Mix conversational Hindi with clear English "
                "technical phrasing; do not write Hindi-only sentences or "
                "translate programming terminology. Keep words such as loop, "
                "iteration, iterable, element, variable, function, syntax, "
                "output, index, condition, list, tuple, and range in English. "
                "Prefer phrases like 'elements par iterate karna', 'code ko "
                "repeat karna', and 'list ke har element ko one by one access "
                "karna'. Avoid unnatural phrases like 'elements ko chalana', "
                "'index ko badhate rehna', or 'loop ko chalana'."
            ),
        }[self.language_preference]
        lesson_guidance = (
            "Guided teaching: be conversational, answer the question first, "
            "start simply, and cover one concept at a time. Use a real-world "
            "analogy only when helpful and connect it back to the correct "
            "concept. For coding, give a small example and explain its key "
            "part; show output when useful. Check understanding with one "
            "small question when appropriate, then wait rather than moving "
            "ahead. Adapt to the student's current level and their latest "
            "message. When confused, explain differently and more simply. "
            "When an answer is correct, acknowledge why and progress gradually. "
            "When it is incorrect, identify the gap, give a small hint, and let "
            "the student try again instead of revealing the full answer. Keep "
            "the interaction in the selected language."
        )
        details = [
            language_guidance,
            lesson_guidance,
            f"level={self.level}",
            f"difficulty={self.difficulty}",
            f"style={self.teaching_style}",
            f"quiz_mode={self.quiz_mode}",
            f"attempts={self.attempts}",
            f"questions_answered={self.questions_answered}",
            f"correct_answers={self.correct_answers}",
        ]
        if self.subject is not None:
            details.append(f"subject={self.subject.value}")
        if self.topic:
            details.append(f"topic={self.topic}")
        if self.current_concept:
            details.append(f"current_concept={self.current_concept}")
        if self.current_question:
            details.append(f"your_previous_question={self.current_question}")
        if self._hint_requested:
            details.append("hint requested: do not reveal the answer")
        if self.last_turn_was_answer_attempt:
            correctness = (
                "correct"
                if self.last_turn_answer_correct is True
                else "incorrect"
                if self.last_turn_answer_correct is False
                else "uncertain"
            )
            details.append(
                "current student turn is an answer attempt; evaluate it now "
                f"(classifier assessment: {correctness})"
            )
        return "Current session-local lesson state: " + "; ".join(details)

    def _adjust_difficulty(self, change: int) -> None:
        current = _LEVELS.index(self.difficulty)
        selected = min(max(current + change, 0), len(_LEVELS) - 1)
        self.difficulty = _LEVELS[selected]
        self.level = self.difficulty
