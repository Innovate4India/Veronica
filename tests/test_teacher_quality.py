"""Deterministic quality checks and bounded recovery for Teacher responses."""

import unittest
from unittest.mock import Mock

from app.ai import AIProvider, AIService, AIServiceError, TeachingLanguage, ToolCall
from app.ai.teacher_quality import (
    safe_teacher_response,
    teacher_quality_guidance,
    teacher_retry_instruction,
    validate_teacher_response,
)

_QUESTION = "Explain the difference between a for loop and a while loop."
_VALID_COMPARISON = """\
A `for` loop iterates over an iterable such as a list. A `while` loop repeats
while its condition is true. Use `for` for collections and `while` when
repetition depends on a condition.

```python
fruits = ["apple", "banana", "cherry"]

for fruit in fruits:
    print(fruit)
```

Output:
```
apple
banana
cherry
```
The `fruit` variable receives each element one by one; a for loop does not
require an index.

```python
count = 1

while count <= 3:
    print(count)
    count += 1
```

Output: 1, 2, 3. Updating `count` eventually makes the condition false; without
an appropriate state change, a while loop can be infinite.

Quick check: which loop is controlled by a condition?
"""


class TeacherResponseValidationTests(unittest.TestCase):
    def test_tutor_guidance_covers_explanation_to_next_step(self) -> None:
        guidance = " ".join(teacher_quality_guidance().casefold().split())

        for instruction in (
            "answer the actual question",
            "analogy",
            "one small example",
            "understanding check",
            "wait",
            "evaluate an attempted answer",
            "give a small hint",
            "different analogy or example",
            "move forward gradually",
        ):
            with self.subTest(instruction=instruction):
                self.assertIn(instruction, guidance)

    def test_accepts_accurate_for_while_comparison_and_examples(self) -> None:
        result = validate_teacher_response(
            _QUESTION,
            _VALID_COMPARISON,
            TeachingLanguage.ENGLISH,
        )

        self.assertTrue(result.is_valid, result.issues)

    def test_rejects_malformed_hinglish_and_incorrect_loop_claims(self) -> None:
        response = _VALID_COMPARISON.replace(
            "A `for` loop iterates over an iterable",
            "Dono use isliye kiya ja sakta hai. A `for` loop requires an index",
        )

        result = validate_teacher_response(
            _QUESTION,
            response,
            TeachingLanguage.HINGLISH,
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("unnatural Hinglish" in issue for issue in result.issues))
        self.assertTrue(any("does not require an index" in issue for issue in result.issues))

    def test_rejects_repeated_sentences_and_invalid_python(self) -> None:
        response = _VALID_COMPARISON.replace(
            "for fruit in fruits:",
            "For fruit in Fruits:",
        ).replace(
            "Quick check: which loop is controlled by a condition?",
            "Loops repeat code. Loops repeat code. Loops repeat code.",
        )

        result = validate_teacher_response(
            _QUESTION,
            response,
            TeachingLanguage.ENGLISH,
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("lowercase" in issue for issue in result.issues))
        self.assertTrue(any("repeated" in issue for issue in result.issues))
        self.assertTrue(any("malformed Python" in issue for issue in result.issues))

    def test_range_explanation_rejects_off_by_one_claim(self) -> None:
        accurate = "range(1, 6) produces 1, 2, 3, 4, 5."
        inaccurate = "range(1, 6) produces 0 to 5."

        self.assertTrue(
            validate_teacher_response(
                "Explain range(1, 6).",
                accurate,
                TeachingLanguage.ENGLISH,
            ).is_valid
        )
        self.assertFalse(
            validate_teacher_response(
                "Explain range(1, 6).",
                inaccurate,
                TeachingLanguage.ENGLISH,
            ).is_valid
        )

    def test_safe_comparison_fallback_is_technically_valid(self) -> None:
        fallback = safe_teacher_response(TeachingLanguage.ENGLISH, _QUESTION)

        self.assertTrue(
            validate_teacher_response(
                _QUESTION,
                fallback,
                TeachingLanguage.ENGLISH,
            ).is_valid
        )

    def test_retry_instruction_preserves_inferred_language_in_auto_mode(self) -> None:
        validation = validate_teacher_response(
            _QUESTION,
            "For fruit in Fruits:",
            TeachingLanguage.AUTO,
        )

        instruction = teacher_retry_instruction(
            validation,
            TeachingLanguage.AUTO,
            "Yaar, for loop aur while loop mein kya difference hai?",
        )

        self.assertIn("hinglish", instruction)
        self.assertIn("Correct every issue", instruction)


class TeacherResponsePipelineTests(unittest.TestCase):
    def test_valid_teacher_answer_uses_one_provider_response(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = _VALID_COMPARISON
        tool_service = Mock()
        service = AIService(provider, tool_calling_service=tool_service)

        result = service.respond(_QUESTION)

        self.assertEqual(result, _VALID_COMPARISON.strip())
        provider.generate_response.assert_called_once()
        self.assertIn(
            "Teacher response quality",
            provider.generate_response.call_args.args[0][0]["content"],
        )
        tool_service.respond.assert_not_called()

    def test_invalid_answer_gets_exactly_one_language_preserving_retry(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            "Dono use isliye kiya ja sakta hai. For fruit in Fruits:",
            _VALID_COMPARISON,
        ]
        tool_service = Mock()
        service = AIService(provider, tool_calling_service=tool_service)

        result = service.respond("Explain the difference between a for loop and a while loop in English.")

        self.assertEqual(result, _VALID_COMPARISON.strip())
        self.assertEqual(provider.generate_response.call_count, 2)
        retry_prompt = provider.generate_response.call_args_list[1].args[0][0][
            "content"
        ]
        self.assertIn("english", retry_prompt)
        self.assertIn("unnatural Hinglish", retry_prompt)
        tool_service.respond.assert_not_called()

    def test_invalid_retry_returns_safe_fallback_without_another_retry(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            "Unrelated answer.",
            "Still unrelated.",
        ]
        service = AIService(provider)

        result = service.respond(_QUESTION)

        self.assertEqual(provider.generate_response.call_count, 2)
        self.assertNotEqual(result, "Still unrelated.")
        self.assertTrue(
            validate_teacher_response(
                _QUESTION,
                result,
                TeachingLanguage.ENGLISH,
            ).is_valid
        )

    def test_raw_tool_call_json_is_never_returned_as_teacher_prose(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = (
            '{"name":"system_info","parameters":{"category":"overview"}}'
        )
        provider.parse_tool_call_text = Mock(
            return_value=ToolCall(
                "system_info",
                {"category": "overview"},
            )
        )
        service = AIService(provider)

        with self.assertRaisesRegex(AIServiceError, "tool-call envelope"):
            service.respond("Teach me Python loops.")


if __name__ == "__main__":
    unittest.main()
