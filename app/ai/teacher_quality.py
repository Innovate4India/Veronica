"""Validation and bounded recovery for Teacher-mode responses."""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass

from app.ai.roles import TeachingLanguage

_FOR_WHILE_QUESTION = re.compile(
    r"\b(?:difference|differ|compare|versus|vs\.?)\b.{0,100}\bfor\b"
    r".{0,50}\bwhile\b|\bfor\b.{0,100}\bwhile\b.{0,100}"
    r"\b(?:difference|differ|compare|versus|vs\.?)\b",
    re.IGNORECASE | re.DOTALL,
)
_MALFORMED_HINGLISH = (
    "dono use isliye kiya ja sakta hai",
    "elements ko pehchante",
    "loop uski wajah se chalta hai",
)
_BAD_KEYWORD_CASE = re.compile(
    r"(?m)^\s*(?:For\s+\w+\s+in\s+\w+\s*:|While\s+.+:)"
)
_STANDALONE_WHILE = re.compile(r"(?m)^\s*While\s*$")
_CODE_FENCE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.IGNORECASE | re.DOTALL)
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_FOR_LINE = re.compile(r"(?m)^\s*for\s+\w+\s+in\s+\w+\s*:\s*$")
_WHILE_LINE = re.compile(r"(?m)^\s*while\s+.+:\s*$")
_FALSE_INDEX_CLAIM = re.compile(
    r"\bfor\s+(?:a\s+)?loop\b.{0,50}"
    r"\b(?:requires?|needs?|must\s+have)\b"
    r".{0,20}\bindex\b",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class TeacherResponseValidation:
    """Outcome of deterministic checks on one candidate Teacher response."""

    issues: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def teacher_quality_guidance() -> str:
    """Return concise, deterministic quality constraints for Teacher answers."""
    return """\

Teacher response quality:
- Teach conversationally, not like a textbook. Answer the actual question
  directly, then build from the simplest useful explanation at the session's
  current level. Cover one concept at a time and keep the response focused.
- When it genuinely helps, use one familiar real-world analogy, then connect it
  back to the technically correct concept; never let the analogy replace facts.
- For a learning explanation, use a compact flow: simple explanation, why it
  matters when relevant, one small example, the important detail, and one
  understanding check when useful. Avoid a large dump of definitions, examples,
  edge cases, or unrelated next concepts.
- For programming, prefer simple syntax, one small runnable example, expected
  output when helpful, and an explanation of the key line(s). Preserve code
  exactly as code; do not paraphrase it into invalid syntax.
- Ask one small question and then wait. Do not reveal an exercise's answer
  unless the student asks for it. Do not move to another concept in the same
  turn as the understanding check.
- Treat the student's latest message as the priority: evaluate an attempted
  answer instead of restarting the explanation. If correct, acknowledge it,
  briefly explain why, then offer a modest next step when appropriate. If
  incorrect, identify the specific gap, give a small hint, and invite another
  attempt; do not immediately provide the complete answer unless requested.
- If the student says they are confused or do not understand, do not repeat the
  same explanation. Simplify it, choose a different analogy or example, and
  check one small point again.
- Adapt wording and difficulty to the teaching session. Move forward gradually
  only after the student shows understanding; do not mistake silence or an
  unanswered exercise for mastery.
- Use valid, correctly formatted code and show output when it clarifies an example.
- For Python loops: `for` iterates over an iterable and does not require an
  index. `while` repeats while its condition is true; update relevant state so
  the loop can terminate, or warn when an example may become infinite.
- If comparing `for` and `while`, explain their different purposes and include
  one small correct example of each.
- `range(1, 6)` produces 1, 2, 3, 4, 5 (start included, stop excluded);
  `range(6)` produces 0, 1, 2, 3, 4, 5.
- Keep explanations natural in the selected language, avoid repeating ideas,
  and ask at most one short follow-up question.
"""


def validate_teacher_response(
    question: str,
    response: str,
    language: TeachingLanguage,
) -> TeacherResponseValidation:
    """Reject malformed coding explanations and low-quality Teacher output."""
    del language
    issues: list[str] = []
    folded = response.casefold()
    if not response.strip():
        issues.append("response is empty.")

    for phrase in _MALFORMED_HINGLISH:
        if phrase in folded:
            issues.append(f"contains unnatural Hinglish phrase: {phrase}")

    if _BAD_KEYWORD_CASE.search(response):
        issues.append("Python keywords for and while must be lowercase.")
    if _STANDALONE_WHILE.search(response):
        issues.append("A while statement must have a condition and colon.")

    sentences = [
        " ".join(sentence.casefold().split())
        for sentence in _SENTENCE.split(response)
        if len(sentence.split()) >= 3
    ]
    repeated = [
        sentence
        for sentence, count in Counter(sentences).items()
        if count > 1
    ]
    words = re.findall(r"[a-z0-9_]+", folded)
    repeated_ngrams = any(
        count >= 3
        for count in Counter(
            tuple(words[index : index + 6])
            for index in range(max(0, len(words) - 5))
        ).values()
    )
    if repeated or repeated_ngrams:
        issues.append("contains repeated sentences.")

    if _FOR_WHILE_QUESTION.search(question):
        _validate_for_while_answer(response, issues)

    if re.search(r"range\s*\(\s*1\s*,\s*6\s*\)", folded):
        range_match = re.search(
            r"range\s*\(\s*1\s*,\s*6\s*\)(.*?)(?=range\s*\(|[.!?\n]|$)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        range_explanation = (
            range_match.group(1).casefold() if range_match is not None else ""
        )
        compact = re.sub(r"\s+", "", range_explanation)
        if not re.search(
            r"(?:1,2,3,4,5|1(?:to|through|-)5)",
            compact,
        ):
            issues.append("range(1, 6) must be explained as 1, 2, 3, 4, 5.")
        if re.search(r"(?:0(?:to|-)5|0,1,2,3,4,5)", compact):
            issues.append("range(1, 6) must not be described as 0 to 5.")

    index_claim = _FALSE_INDEX_CLAIM.search(response.replace("`", ""))
    if index_claim is not None and not re.search(
        r"\b(?:(?:does\s+not|doesn't)\s+(?:require|need)|need\s+not|"
        r"needs?\s+no|never|not\s+require)\b",
        index_claim.group(0),
        re.IGNORECASE,
    ):
        issues.append("a for loop does not require an index.")

    return TeacherResponseValidation(tuple(dict.fromkeys(issues)))


def teacher_retry_instruction(
    validation: TeacherResponseValidation,
    language: TeachingLanguage,
    question: str = "",
) -> str:
    """Return one bounded regeneration instruction preserving language choice."""
    issue_list = "\n".join(f"- {issue}" for issue in validation.issues)
    response_language = language
    if response_language is TeachingLanguage.AUTO:
        response_language = _infer_language(question)
    return (
        "Your previous Teacher response failed deterministic quality checks. "
        "Rewrite the complete answer once, directly answering the student's "
        "question. Preserve the selected response language exactly: "
        f"{response_language.value}. Do not change language. Correct every issue below:\n"
        f"{issue_list}\n"
        "For a for-versus-while question, directly compare iterable-based "
        "iteration with condition-based repetition and include valid lowercase "
        "Python examples for both. Keep the answer concise and ask at most one "
        "brief follow-up question. Keep the explanation conversational and "
        "appropriate to the current teaching stage; do not restart a lesson "
        "when the student is answering, and do not expose an exercise answer "
        "before the student attempts it. Explain that a for loop does not require an "
        "index. If range(1, 6) is mentioned, say it produces 1, 2, 3, 4, 5 "
        "because the start is included and the stop is excluded; range(6) "
        "produces 0, 1, 2, 3, 4, 5. Do not repeat the previous broken wording."
    )


def safe_teacher_response(
    language: TeachingLanguage,
    question: str,
) -> str:
    """Return a short, known-correct answer after the single retry fails."""
    selected = language
    if selected is TeachingLanguage.AUTO:
        selected = _infer_language(question)

    if _FOR_WHILE_QUESTION.search(question):
        return _for_while_fallback(selected)
    return {
        TeachingLanguage.ENGLISH: (
            "I want to make sure I explain that accurately. Could you ask the "
            "question once more, or tell me which part you want to focus on?"
        ),
        TeachingLanguage.HINDI: (
            "Main ise sahi tarah samjhana chahti hoon. Kya aap apna sawaal "
            "dobara pooch sakte hain ya bata sakte hain ki kis hissa par focus karein?"
        ),
        TeachingLanguage.HINGLISH: (
            "Main isse accurately explain karna chahti hoon. Kya aap apna "
            "question ek baar phir pooch sakte hain?"
        ),
        TeachingLanguage.AUTO: "",
    }[selected]


def _validate_for_while_answer(response: str, issues: list[str]) -> None:
    folded = response.casefold().replace("`", "")
    required_concepts = {
        "for-loop iterable behavior": (
            "for loop" in folded and "iterable" in folded
        ),
        "while-loop condition behavior": (
            "while loop" in folded
            and "condition" in folded
            and "true" in folded
        ),
    }
    for label, present in required_concepts.items():
        if not present:
            issues.append(f"does not explain {label}.")

    code = "\n".join(_CODE_FENCE.findall(response)) or response
    if not _FOR_LINE.search(code):
        issues.append("does not include valid lowercase for-loop syntax.")
    if not _WHILE_LINE.search(code):
        issues.append("does not include a while loop with a condition.")
    compact_code = re.sub(r"\s+", " ", code)
    if (
        'fruits = ["apple", "banana", "cherry"]' not in compact_code
        or "for fruit in fruits:" not in compact_code
        or "print(fruit)" not in compact_code
    ):
        issues.append("for-loop example must use the specified fruits example.")
    if not re.search(
        r"output\s*:?\s*(?:```[^\n]*\n)?\s*apple\s+banana\s+cherry",
        response,
        re.IGNORECASE,
    ):
        issues.append("for-loop example must show apple, banana, cherry output.")
    if (
        "count = 1" not in compact_code
        or "while count <= 3:" not in compact_code
        or "count += 1" not in compact_code
    ):
        issues.append("while-loop example must update count and terminate.")

    for block in _CODE_FENCE.findall(response):
        try:
            ast.parse(block)
        except SyntaxError:
            issues.append("contains malformed Python code.")
            break


def _for_while_fallback(language: TeachingLanguage) -> str:
    if language is TeachingLanguage.ENGLISH:
        intro = (
            "A `for` loop iterates over an iterable; a `while` loop repeats "
            "while its condition is true. Use `for` for a collection or known "
            "iteration pattern, and `while` when repetition depends on a condition."
        )
        comparison = "Both loop examples:"
        check = "Quick check: which loop is driven by a condition?"
        fruit_explanation = (
            "`fruit` receives each next element; this `for` loop needs no index."
        )
        while_explanation = (
            "`count` changes, so the condition eventually becomes false and the "
            "loop stops. Without a state change, an infinite loop can occur."
        )
        output_label = "Output:"
        while_output = "Output: `1`, `2`, `3`."
    elif language is TeachingLanguage.HINDI:
        intro = (
            "`for` loop किसी iterable (जैसे list, tuple, string या range) के "
            "हर element पर iterate करता है; इसमें index की ज़रूरत नहीं होती। "
            "`while` loop condition के true रहने तक code दोहराता है। Collection "
            "या निश्चित iteration pattern के लिए `for`, और condition पर निर्भर "
            "repetition के लिए `while` उपयोग करें।"
        )
        comparison = "दोनों loops के उदाहरण:"
        check = "छोटा सवाल: कौन-सा loop condition पर निर्भर करता है?"
        fruit_explanation = (
            "`fruit` variable को हर iteration में अगला element मिलता है; "
            "इस `for` loop में index की आवश्यकता नहीं है।"
        )
        while_explanation = (
            "`count` बदलता है, इसलिए condition अंततः false होती है और loop रुकता "
            "है। State न बदले तो infinite loop हो सकता है।"
        )
        output_label = "Output:"
        while_output = "Output: `1`, `2`, `3`."
    else:
        intro = (
            "`for` loop kisi iterable ke items par iterate karta hai; "
            "`while` loop condition true rehne tak code repeat karta hai. "
            "Collection ya known iteration pattern ke liye `for`, aur "
            "condition-based repetition ke liye `while` use karein."
        )
        comparison = "Dono loops ke examples:"
        check = "Quick check: kaunsa loop condition par depend karta hai?"
        fruit_explanation = (
            "`fruit` ko har iteration mein next element milta hai; "
            "is `for` loop ke liye index ki zaroorat nahi."
        )
        while_explanation = (
            "`count` update hota hai, isliye condition eventually false hoti hai "
            "aur loop stop hota hai. State update na ho to infinite loop ho sakta hai."
        )
        output_label = "Output:"
        while_output = "Output: `1`, `2`, `3`."
    return (
        intro
        + "\n\n"
        + comparison
        + "\n\n```python\n"
        + 'fruits = ["apple", "banana", "cherry"]\n\n'
        + "for fruit in fruits:\n"
        + "    print(fruit)\n"
        + "```\n"
        + output_label
        + "\n```\napple\nbanana\ncherry\n```\n"
        + fruit_explanation
        + "\n\n"
        + "```python\n"
        + "count = 1\n\n"
        + "while count <= 3:\n"
        + "    print(count)\n"
        + "    count += 1\n"
        + "```\n"
        + while_output
        + " "
        + while_explanation
        + "\n\n"
        + check
    )


def _infer_language(question: str) -> TeachingLanguage:
    if re.search(r"[\u0900-\u097f]", question):
        return TeachingLanguage.HINDI
    hinglish_markers = (
        "kya",
        "kaise",
        "hai",
        "mein",
        "samjhao",
        "batao",
    )
    if any(marker in question.casefold().split() for marker in hinglish_markers):
        return TeachingLanguage.HINGLISH
    return TeachingLanguage.ENGLISH
