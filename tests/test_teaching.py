"""Tests for session-local teacher progress."""

import unittest

from app.ai import (
    RoleDecision,
    TeachingLanguage,
    TeachingSession,
    TeachingSubject,
    VeronicaRole,
)


class TeachingSessionTests(unittest.TestCase):
    def test_language_preference_defaults_to_auto_and_resets_with_session(self) -> None:
        session = TeachingSession()
        self.assertEqual(session.language_preference, TeachingLanguage.AUTO)

        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, topic="Python"),
            role=VeronicaRole.TEACHER,
        )
        session.set_language_preference(TeachingLanguage.HINGLISH)
        session.request_reset()

        self.assertEqual(session.language_preference, TeachingLanguage.AUTO)

    def test_tracks_lesson_subject_topic_and_level_in_memory(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(
                VeronicaRole.TEACHER,
                subject=TeachingSubject.CODING,
                topic="Python loops",
                level="intermediate",
            ),
            role=VeronicaRole.TEACHER,
        )

        self.assertTrue(session.active)
        self.assertEqual(session.subject, TeachingSubject.CODING)
        self.assertEqual(session.topic, "Python loops")
        self.assertEqual(session.level, "intermediate")
        self.assertIsNotNone(session.started_at)
        self.assertIn("topic=Python loops", session.prompt_context())

    def test_tracks_question_attempt_and_correctness(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, topic="Python"),
            role=VeronicaRole.TEACHER,
        )
        session.record_assistant_response("What does a for-loop repeat?")
        self.assertEqual(session.current_question, "What does a for-loop repeat?")

        session.apply_decision(
            RoleDecision(
                VeronicaRole.TEACHER,
                answer_attempt=True,
                answer_correct=True,
            ),
            role=VeronicaRole.TEACHER,
        )
        self.assertEqual(session.attempts, 1)
        self.assertEqual(session.questions_answered, 1)
        self.assertEqual(session.correct_answers, 1)
        self.assertIsNone(session.current_question)
        self.assertTrue(session.last_turn_was_answer_attempt)
        self.assertTrue(session.last_turn_answer_correct)
        self.assertIn(
            "current student turn is an answer attempt",
            session.prompt_context(),
        )

    def test_incorrect_answer_context_guides_hint_and_retry(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, topic="Python"),
            role=VeronicaRole.TEACHER,
        )
        session.record_assistant_response("What does print(x) display?")

        session.apply_decision(
            RoleDecision(
                VeronicaRole.TEACHER,
                answer_attempt=True,
                answer_correct=False,
            ),
            role=VeronicaRole.TEACHER,
        )

        context = session.prompt_context()
        self.assertIn("classifier assessment: incorrect", context)
        self.assertIn("give a small hint", context)
        self.assertIn("let the student try again", context)
        self.assertNotIn("your_previous_question=", context)

        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER),
            role=VeronicaRole.TEACHER,
        )
        self.assertFalse(session.last_turn_was_answer_attempt)
        self.assertIsNone(session.last_turn_answer_correct)

    def test_reset_clears_last_answer_assessment(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(
                VeronicaRole.TEACHER,
                answer_attempt=True,
                answer_correct=False,
            ),
            role=VeronicaRole.TEACHER,
        )

        session.request_reset()

        self.assertFalse(session.last_turn_was_answer_attempt)
        self.assertIsNone(session.last_turn_answer_correct)

    def test_hint_and_quiz_requests_change_teaching_style(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, request_hint=True),
            role=VeronicaRole.TEACHER,
        )
        self.assertEqual(session.teaching_style, "hint-first")
        self.assertIn("hint requested", session.prompt_context())

        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, quiz_mode=True),
            role=VeronicaRole.TEACHER,
        )
        self.assertTrue(session.quiz_mode)
        self.assertEqual(session.teaching_style, "quiz")

    def test_difficulty_adapts_only_after_repeated_results(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, level="beginner"),
            role=VeronicaRole.TEACHER,
        )
        session.record_answer(True)
        session.record_answer(True)
        self.assertEqual(session.difficulty, "beginner")
        session.record_answer(True)
        self.assertEqual(session.difficulty, "intermediate")
        session.record_answer(False)
        self.assertEqual(session.difficulty, "intermediate")
        session.record_answer(False)
        self.assertEqual(session.difficulty, "beginner")

    def test_leaving_teacher_role_pauses_active_session(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(VeronicaRole.TEACHER, topic="Python"),
            role=VeronicaRole.TEACHER,
        )
        session.apply_decision(
            RoleDecision(VeronicaRole.FRIEND),
            role=VeronicaRole.FRIEND,
        )
        self.assertFalse(session.active)
        self.assertEqual(session.topic, "Python")

    def test_reset_clears_all_session_progress(self) -> None:
        session = TeachingSession()
        session.apply_decision(
            RoleDecision(
                VeronicaRole.TEACHER,
                subject=TeachingSubject.ENGLISH,
                topic="conversation",
                quiz_mode=True,
            ),
            role=VeronicaRole.TEACHER,
        )
        session.record_answer(True)

        session.request_reset()

        self.assertFalse(session.active)
        self.assertIsNone(session.subject)
        self.assertIsNone(session.topic)
        self.assertEqual(session.attempts, 0)
        self.assertEqual(session.questions_answered, 0)
        self.assertEqual(session.correct_answers, 0)
        self.assertFalse(session.quiz_mode)
        self.assertIsNone(session.started_at)
        self.assertIn("No lesson is active", session.prompt_context())


if __name__ == "__main__":
    unittest.main()
