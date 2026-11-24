"""Tests for Veronica's conversational role selection."""

import json
import unittest
from unittest.mock import Mock

from app.ai import (
    AIProvider,
    AIService,
    AIServiceError,
    OllamaAssistantResponse,
    OllamaToolCall,
    OllamaToolCallingService,
    ToolCall,
    RoleDecision,
    TeachingLanguage,
    TeachingSubject,
    VeronicaRole,
)
from app.ai.roles import (
    classify_role,
    explicit_role_command,
    role_instructions,
    teaching_language_from_message,
)
from app.tools import JSONValue, ParameterSchema, Tool, ToolRegistry


def _classification(role: str, **overrides: object) -> str:
    value: dict[str, object] = {
        "role": role,
        "subject": None,
        "topic": None,
        "level": None,
        "quiz_mode": False,
        "answer_attempt": False,
        "answer_correct": None,
        "request_hint": False,
    }
    value.update(overrides)
    return json.dumps(value)


class _RecordingTool(Tool):
    def __init__(self, name: str, parameter_name: str | None) -> None:
        self._name = name
        self._parameter_name = parameter_name
        self.execute_mock = Mock(return_value={"executed": name})

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Test {self._name} execution."

    @property
    def parameters_schema(self) -> ParameterSchema:
        return {
            "type": "object",
            "properties": (
                {self._parameter_name: {"type": "string"}}
                if self._parameter_name is not None
                else {}
            ),
            "required": (
                [self._parameter_name]
                if self._parameter_name is not None
                else []
            ),
            "additionalProperties": False,
        }

    def execute(self, parameters: dict[str, JSONValue]) -> JSONValue:
        return self.execute_mock(parameters)


class RoleSelectionTests(unittest.TestCase):
    def test_explicit_mode_commands_select_roles_without_model_call(self) -> None:
        cases = (
            ("Teacher mode", VeronicaRole.TEACHER),
            ("Friend mode", VeronicaRole.FRIEND),
            ("Assistant mode", VeronicaRole.ASSISTANT),
        )
        for command, expected in cases:
            with self.subTest(command=command):
                provider = Mock(spec=AIProvider)
                self.assertEqual(explicit_role_command(command), expected)
                decision = classify_role(
                    provider,
                    command,
                    [],
                    preferred_role=VeronicaRole.ASSISTANT,
                    teaching_context="",
                )
                self.assertEqual(decision.role, expected)
                provider.generate_response.assert_not_called()

    def test_model_classifies_friend_teacher_and_assistant_intents(self) -> None:
        for role in VeronicaRole:
            with self.subTest(role=role):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = _classification(role.value)
                decision = classify_role(
                    provider,
                    "Please help me with this.",
                    [],
                    preferred_role=VeronicaRole.ASSISTANT,
                    teaching_context="",
                )
                self.assertEqual(decision.role, role)

    def test_teaching_request_uses_teacher_without_keyword_only_routing(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = _classification(
            "teacher",
            subject="coding",
            topic="Python",
            level="beginner",
        )
        decision = classify_role(
            provider,
            "I want to understand how Python functions work.",
            [],
            preferred_role=VeronicaRole.FRIEND,
            teaching_context="",
        )
        self.assertEqual(
            decision,
            RoleDecision(
                role=VeronicaRole.TEACHER,
                subject=TeachingSubject.CODING,
                topic="Python",
                level="beginner",
            ),
        )
        self.assertEqual(provider.generate_response.call_count, 1)

    def test_explicit_teacher_request_infers_topic_and_quiz_mode(self) -> None:
        provider = Mock(spec=AIProvider)
        decision = classify_role(
            provider,
            "Quiz me on Python",
            [],
            preferred_role=VeronicaRole.ASSISTANT,
            teaching_context="",
        )
        self.assertEqual(decision.role, VeronicaRole.TEACHER)
        self.assertEqual(decision.topic, "Python")
        self.assertTrue(decision.quiz_mode)
        provider.generate_response.assert_not_called()

    def test_casual_messages_stay_in_friend_without_tools(self) -> None:
        casual_messages = (
            "Hey Veronica, how are you?",
            "Hi Veronica",
            "How was your day?",
            "I'm bored",
            "College was boring today",
            "Let's just talk",
            "Yaar aaj college bahut boring tha",
        )
        for message in casual_messages:
            with self.subTest(message=message):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = "I'm glad we're chatting."
                tool_service = Mock()
                service = AIService(provider, tool_calling_service=tool_service)

                response = service.respond(message)

                self.assertEqual(response, "I'm glad we're chatting.")
                self.assertEqual(service.role, VeronicaRole.FRIEND)
                tool_service.respond.assert_not_called()
                provider.generate_response.assert_called_once()
                system_prompt = provider.generate_response.call_args.args[0][0][
                    "content"
                ]
                self.assertIn("CURRENT ROLE: FRIEND", system_prompt)
                self.assertNotIn("system_info", system_prompt)
                self.assertNotIn("app_launcher", system_prompt)
                self.assertNotIn("screen_understanding", system_prompt)

    def test_general_assistant_question_does_not_expose_tools(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            _classification("assistant"),
            "A simple answer.",
        ]
        tool_service = Mock()
        service = AIService(provider, tool_calling_service=tool_service)

        self.assertEqual(service.respond("Why is the sky blue?"), "A simple answer.")

        tool_service.respond.assert_not_called()
        self.assertEqual(provider.generate_response.call_count, 2)

    def test_explicit_computer_requests_still_reach_their_registered_tools(self) -> None:
        cases = (
            ("What's my CPU?", "system_info", "metric", "cpu"),
            ("Open VS Code", "app_launcher", "application", "VS Code"),
            (
                "What's on my screen?",
                "screen_understanding",
                "question",
                "What's on my screen?",
            ),
            ("Take a screenshot", "screenshot", None, None),
            ("Calculate 25 * 8", "calculator", "expression", "25 * 8"),
        )
        for user_message, tool_name, parameter_name, argument in cases:
            with self.subTest(tool_name=tool_name):
                provider = Mock()
                provider.generate_response.return_value = _classification("assistant")
                arguments = (
                    {parameter_name: argument}
                    if parameter_name is not None
                    else {}
                )
                provider.generate_tool_response.side_effect = [
                    OllamaAssistantResponse(
                        "",
                        (
                            OllamaToolCall(
                                tool_name,
                                arguments,
                            ),
                        ),
                    ),
                    OllamaAssistantResponse("Done."),
                ]
                tool = _RecordingTool(tool_name, parameter_name)
                registry = ToolRegistry()
                registry.register(tool)
                service = AIService(
                    provider,
                    tool_calling_service=OllamaToolCallingService(
                        provider,
                        registry,
                    ),
                )

                response = service.respond(user_message)

                self.assertEqual(response, "Done.")
                self.assertEqual(service.role, VeronicaRole.ASSISTANT)
                tool.execute_mock.assert_called_once_with(arguments)
                definitions = provider.generate_tool_response.call_args_list[0].args[1]
                self.assertEqual(definitions[0]["function"]["name"], tool_name)

    def test_teaching_turns_stay_text_only_even_with_tools_available(self) -> None:
        requests = (
            "Veronica, teach me Python loops from the beginning.",
            "Explain DSA arrays.",
            "Teach me HTML.",
            "Help me learn SQL.",
            "Quiz me on Python.",
            "Explain recursion in simple language.",
        )
        for request in requests:
            with self.subTest(request=request):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = (
                    "A loop repeats instructions. For example, "
                    "`for item in items` visits each item. What does it repeat?"
                )
                tool_service = Mock()
                service = AIService(provider, tool_calling_service=tool_service)

                answer = service.respond(request)

                self.assertIn("loop repeats", answer)
                self.assertEqual(service.role, VeronicaRole.TEACHER)
                self.assertTrue(service.teaching_session.active)
                self.assertIsNotNone(service.teaching_session.current_question)
                self.assertIn("CURRENT ROLE: TEACHER", provider.generate_response.call_args.args[0][0]["content"])
                tool_service.respond.assert_not_called()

    def test_teacher_language_commands_and_auto_mode(self) -> None:
        cases = (
            (
                "Teach me Python loops in English.",
                TeachingLanguage.ENGLISH,
                "every teaching explanation",
            ),
            (
                "Teach me Python loops in Hindi.",
                TeachingLanguage.HINDI,
                "in Hindi",
            ),
            (
                "Teach me Python loops in Hinglish.",
                TeachingLanguage.HINGLISH,
                "Latin-script Hinglish",
            ),
        )
        for message, expected, prompt_text in cases:
            with self.subTest(language=expected):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = "Let's learn loops."
                tool_service = Mock()
                service = AIService(provider, tool_calling_service=tool_service)

                service.respond(message)

                self.assertEqual(service.role, VeronicaRole.TEACHER)
                self.assertEqual(
                    service.teaching_session.language_preference,
                    expected,
                )
                prompt = provider.generate_response.call_args.args[0][0]["content"]
                self.assertIn(prompt_text, prompt)
                tool_service.respond.assert_not_called()

        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = "Chalo loops seekhte hain."
        service = AIService(provider)
        service.respond("Teach me Python loops.")
        self.assertEqual(
            service.teaching_session.language_preference,
            TeachingLanguage.AUTO,
        )
        prompt = provider.generate_response.call_args.args[0][0]["content"]
        self.assertIn("AUTO language: follow the user's language and style", prompt)
        self.assertIn("Do not switch languages without a reason", prompt)

    def test_hinenglish_aliases_normalize_to_hinglish(self) -> None:
        for message in (
            "Teach me Python loops in hinEnglish.",
            "Hinglish",
            "Hinglish mode",
            "Hindi + English",
            "Switch to hinEnglish",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    teaching_language_from_message(message),
                    TeachingLanguage.HINGLISH,
                )

        for message in (
            "Teach me Python loops in hinEnglish.",
            "Teach me Python loops in Hindi + English.",
        ):
            with self.subTest(teacher_request=message):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = (
                    "Python mein loops ka use code ko repeatedly run karne ke "
                    "liye hota hai."
                )
                service = AIService(provider)

                service.respond(message)

                self.assertEqual(service.role, VeronicaRole.TEACHER)
                self.assertEqual(
                    service.teaching_session.language_preference,
                    TeachingLanguage.HINGLISH,
                )

    def test_hinglish_teacher_guidance_is_natural_and_technically_accurate(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = (
            "Python mein loops ka use kisi piece of code ko repeatedly run "
            "karne ke liye hota hai."
        )
        service = AIService(provider)

        service.respond("Teach me Python loops from the beginning in hinEnglish.")

        prompt = provider.generate_response.call_args.args[0][0]["content"]
        self.assertIn("HINGLISH language: use natural, student-friendly", prompt)
        self.assertIn("elements par iterate karna", prompt)
        self.assertIn("code ko repeat karna", prompt)
        self.assertIn("list ke har element ko one by one access karna", prompt)
        self.assertIn("Avoid unnatural phrases like", prompt)
        self.assertIn("elements ko chalana", prompt)
        self.assertIn("index ko badhate rehna", prompt)
        self.assertIn("loop ko chalana", prompt)
        self.assertIn("it does not require an index", prompt)
        self.assertIn("variable `fruit` receives each element one by one", prompt)
        self.assertNotIn("for loop requires an index", prompt.casefold())
        self.assertIn("the start is included", prompt)
        self.assertIn("range(1, 6) yields 1, 2, 3, 4, 5", prompt)
        self.assertIn("range(6) yields 0, 1, 2, 3, 4, 5", prompt)

    def test_beginner_coding_lesson_is_short_and_waits_for_answer(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = (
            "Python mein `for` loop iterable ke elements par iterate karta hai. "
            "Syntax: `for item in items:`. Example: `for fruit in fruits: "
            "print(fruit)`. Output mein har fruit alag line par aata hai. "
            "Quick check: `fruit` variable mein har iteration par kya value aati hai?"
        )
        service = AIService(provider)

        answer = service.respond("Teach me Python loops from the beginning in hinEnglish.")

        prompt = " ".join(
            provider.generate_response.call_args.args[0][0]["content"].split()
        )
        self.assertIn("answer the question first, start simply", prompt)
        self.assertIn("small example and explain its key part", prompt)
        self.assertIn("show output when useful", prompt)
        self.assertIn("one small question when appropriate", prompt)
        self.assertIn("wait rather than moving ahead", prompt)
        self.assertIn("Do not reveal an exercise's answer", prompt)
        self.assertIn("Quick check:", answer)
        self.assertIsNotNone(service.teaching_session.current_question)
        self.assertNotIn("The answer is", answer)

    def test_english_and_hindi_guidance_remain_in_the_selected_language(self) -> None:
        cases = (
            ("Teach me Python loops in English.", "ENGLISH language:", "in English"),
            ("Teach me Python loops in Hindi.", "HINDI language:", "primarily in Hindi"),
        )
        for message, language_marker, requirement in cases:
            with self.subTest(language=language_marker):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = "Teaching response."
                service = AIService(provider)

                service.respond(message)

                prompt = provider.generate_response.call_args.args[0][0]["content"]
                self.assertIn(language_marker, prompt)
                self.assertIn(requirement, prompt)

    def test_language_change_keeps_active_lesson_and_does_not_change_friend_role(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            "A loop repeats code. What does it repeat?",
            "Language changed. What does a loop repeat?",
        ]
        tool_service = Mock()
        service = AIService(provider, tool_calling_service=tool_service)
        service.respond("Teach me Python loops.")
        previous_question = service.teaching_session.current_question
        started_at = service.teaching_session.started_at

        service.respond("Switch to English")

        self.assertEqual(service.role, VeronicaRole.TEACHER)
        self.assertTrue(service.teaching_session.active)
        self.assertEqual(service.teaching_session.topic, "Python")
        self.assertEqual(service.teaching_session.started_at, started_at)
        self.assertIsNotNone(service.teaching_session.current_question)
        self.assertNotEqual(
            service.teaching_session.current_question,
            previous_question,
        )
        self.assertEqual(
            service.teaching_session.language_preference,
            TeachingLanguage.ENGLISH,
        )
        prompt = provider.generate_response.call_args_list[-1].args[0][0]["content"]
        self.assertIn("ENGLISH language:", prompt)
        tool_service.respond.assert_not_called()

        friend_provider = Mock(spec=AIProvider)
        friend_provider.generate_response.return_value = (
            "Sure, Hinglish from now on."
        )
        friend_service = AIService(
            friend_provider,
            tool_calling_service=tool_service,
        )
        friend_service.respond("Hey Veronica, how are you?")
        friend_service.respond("Switch to Hinglish")
        self.assertEqual(friend_service.role, VeronicaRole.FRIEND)
        self.assertFalse(friend_service.teaching_session.active)
        self.assertEqual(
            friend_service.teaching_session.language_preference,
            TeachingLanguage.HINGLISH,
        )
        tool_service.respond.assert_not_called()

    def test_language_mode_commands_select_language_without_starting_other_roles(self) -> None:
        cases = (
            ("English mode", TeachingLanguage.ENGLISH),
            ("Use Hindi", TeachingLanguage.HINDI),
            ("Use Hinglish", TeachingLanguage.HINGLISH),
            ("Use my language", TeachingLanguage.AUTO),
        )
        for command, expected in cases:
            with self.subTest(command=command):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = (
                    "A loop repeats code. What does it repeat?"
                )
                service = AIService(provider)
                service.respond("Teach me Python loops.")

                service.respond(command)

                self.assertEqual(service.role, VeronicaRole.TEACHER)
                self.assertTrue(service.teaching_session.active)
                self.assertEqual(service.teaching_session.topic, "Python")
                self.assertEqual(
                    service.teaching_session.language_preference,
                    expected,
                )

    def test_language_preference_does_not_authorize_tools(self) -> None:
        for command in (
            "English mode",
            "Teach me in Hindi",
            "Use Hinglish",
            "Use my language",
        ):
            with self.subTest(command=command):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = (
                    "A language preference was updated."
                )
                tool_service = Mock()
                service = AIService(provider, tool_calling_service=tool_service)

                service.respond(command)

                tool_service.respond.assert_not_called()

    def test_answer_evaluation_uses_selected_teacher_language(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            "A loop repeats code. What does it repeat?",
            _classification(
                "teacher",
                answer_attempt=True,
                answer_correct=True,
            ),
            "Correct! A loop repeats code. What does a for-loop iterate over?",
        ]
        service = AIService(provider)
        service.respond("Teach me Python loops in English.")

        answer = service.respond("It repeats code.")

        self.assertIn("Correct!", answer)
        response_prompt = provider.generate_response.call_args_list[2].args[0][0][
            "content"
        ]
        normalized_prompt = " ".join(response_prompt.split())
        self.assertIn("ENGLISH language:", normalized_prompt)
        self.assertIn("current student turn is an answer attempt", normalized_prompt)
        self.assertIn(
            "evaluate an attempted answer instead of restarting",
            normalized_prompt,
        )
        self.assertIn("give a small hint", normalized_prompt)
        self.assertEqual(service.teaching_session.attempts, 1)

    def test_teacher_prompt_encourages_accurate_python_range_explanations(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = (
            "`range(1, 6)` generates 1, 2, 3, 4, 5 because 1 is included and "
            "6 is excluded. `range(6)` generates 0, 1, 2, 3, 4, 5."
        )
        service = AIService(provider)

        answer = service.respond("Explain Python range in English.")

        self.assertIn("range(1, 6)", answer)
        self.assertIn("1, 2, 3, 4, 5", answer)
        self.assertIn("range(6)", answer)
        prompt = provider.generate_response.call_args.args[0][0]["content"]
        self.assertIn("the start is included and the stop is excluded", prompt)
        self.assertIn("range(1, 6) yields 1, 2, 3, 4, 5", prompt)
        self.assertIn("range(6) yields 0, 1, 2, 3, 4, 5", prompt)

    def test_explicit_tool_request_during_teaching_is_scoped_to_requested_tool(self) -> None:
        cases = (
            (
                "Teach me Python and calculate 25 * 8",
                "calculator",
                "expression",
                "25 * 8",
            ),
            (
                "Teach me Git and open VS Code",
                "app_launcher",
                "application",
                "VS Code",
            ),
        )
        for user_message, tool_name, parameter_name, argument in cases:
            with self.subTest(tool_name=tool_name):
                provider = Mock()
                arguments = {parameter_name: argument}
                provider.generate_tool_response.side_effect = [
                    OllamaAssistantResponse(
                        "",
                        (OllamaToolCall(tool_name, arguments),),
                    ),
                    OllamaAssistantResponse(
                        "Here is the lesson, along with the requested result."
                    ),
                ]
                tool = _RecordingTool(tool_name, parameter_name)
                unrelated_tool = _RecordingTool("system_info", "metric")
                registry = ToolRegistry()
                registry.register(tool)
                registry.register(unrelated_tool)
                service = AIService(
                    provider,
                    tool_calling_service=OllamaToolCallingService(
                        provider,
                        registry,
                    ),
                )

                answer = service.respond(user_message)

                self.assertIn("lesson", answer)
                self.assertEqual(service.role, VeronicaRole.TEACHER)
                tool.execute_mock.assert_called_once_with(arguments)
                unrelated_tool.execute_mock.assert_not_called()
                definitions = provider.generate_tool_response.call_args_list[0].args[1]
                self.assertEqual(
                    [item["function"]["name"] for item in definitions],
                    [tool_name],
                )

    def test_unrequested_tool_call_during_teaching_is_not_executed(self) -> None:
        provider = Mock()
        provider.generate_tool_response.side_effect = [
            OllamaAssistantResponse(
                "",
                (
                    OllamaToolCall(
                        "system_info",
                        {"metric": "cpu"},
                    ),
                ),
            ),
            OllamaAssistantResponse(
                "Here is the Python lesson and the requested calculation."
            ),
        ]
        calculator = _RecordingTool("calculator", "expression")
        system_info = _RecordingTool("system_info", "metric")
        registry = ToolRegistry()
        registry.register(calculator)
        registry.register(system_info)
        service = AIService(
            provider,
            tool_calling_service=OllamaToolCallingService(provider, registry),
        )

        answer = service.respond("Teach me Python and calculate 25 * 8")

        self.assertIn("lesson", answer)
        calculator.execute_mock.assert_not_called()
        system_info.execute_mock.assert_not_called()
        second_call_messages = provider.generate_tool_response.call_args_list[1].args[0]
        self.assertIn("not explicitly requested", second_call_messages[-1]["content"])

    def test_teacher_answer_is_evaluated_and_state_is_updated(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            "A loop repeats code. What does a loop do?",
            _classification(
                "teacher",
                answer_attempt=True,
                answer_correct=True,
            ),
            "Correct! It repeats code. What does a for-loop iterate over?",
        ]
        tool_service = Mock()
        service = AIService(provider, tool_calling_service=tool_service)

        service.respond("Teach me Python loops.")
        answer = service.respond("It repeats code.")

        self.assertIn("Correct!", answer)
        self.assertEqual(service.role, VeronicaRole.TEACHER)
        self.assertEqual(service.teaching_session.attempts, 1)
        self.assertEqual(service.teaching_session.correct_answers, 1)
        self.assertIsNotNone(service.teaching_session.current_question)
        tool_service.respond.assert_not_called()

    def test_raw_tool_call_json_is_never_returned_as_assistant_prose(self) -> None:
        raw_call = (
            "Here's a JSON function call to begin teaching Python loops:\n\n"
            '{"name":"system_info","parameters":{"category":"overview"}}'
        )
        cases = (
            ("Teach me Python loops.", None),
            ("Teach me Python and calculate 25 * 8", raw_call),
        )
        for user_message, tool_response in cases:
            with self.subTest(user_message=user_message):
                provider = Mock(spec=AIProvider)
                provider.generate_response.return_value = raw_call
                provider.parse_tool_call_text = Mock(
                    return_value=ToolCall(
                        "system_info",
                        {"category": "overview"},
                    )
                )
                tool_service = Mock()
                if tool_response is not None:
                    tool_service.respond.return_value = tool_response
                service = AIService(provider, tool_calling_service=tool_service)

                with self.assertRaisesRegex(AIServiceError, "tool-call envelope"):
                    service.respond(user_message)

                self.assertEqual(service.message_count, 1)

    def test_invalid_classifier_output_falls_back_to_assistant(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = "not json"
        decision = classify_role(
            provider,
            "A request with unclear intent.",
            [],
            preferred_role=VeronicaRole.FRIEND,
            teaching_context="",
        )
        self.assertEqual(decision.role, VeronicaRole.ASSISTANT)

    def test_current_intent_can_switch_role(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.side_effect = [
            _classification("friend"),
            "Nice to chat!",
            "Let's learn Python.",
        ]
        service = AIService(provider)
        service.respond("I had a relaxing weekend.")
        friend_prompt = provider.generate_response.call_args_list[1].args[0][0][
            "content"
        ]
        self.assertIn("CURRENT ROLE: FRIEND", friend_prompt)
        service.respond("I want to learn how Python loops work.")
        self.assertEqual(service.role, VeronicaRole.TEACHER)
        self.assertTrue(service.teaching_session.active)
        prompt = provider.generate_response.call_args_list[2].args[0][0]["content"]
        self.assertIn("CURRENT ROLE: TEACHER", prompt)

    def test_clear_resets_role_and_teaching_progress(self) -> None:
        provider = Mock(spec=AIProvider)
        provider.generate_response.return_value = "Ready to teach."
        service = AIService(provider)
        service.respond("Teacher mode")
        self.assertTrue(service.teaching_session.active)

        service.clear()

        self.assertEqual(service.role, VeronicaRole.ASSISTANT)
        self.assertFalse(service.teaching_session.active)
        self.assertIsNone(service.teaching_session.topic)

    def test_role_guidance_keeps_veronica_identity_and_role_boundaries(self) -> None:
        self.assertIn("Stay Veronica", role_instructions(VeronicaRole.FRIEND))
        teacher = role_instructions(VeronicaRole.TEACHER, "session-local")
        self.assertIn("do not reveal it", teacher)
        self.assertIn("session-local", teacher)
        self.assertIn("never claim unperformed actions", role_instructions(
            VeronicaRole.ASSISTANT
        ))


if __name__ == "__main__":
    unittest.main()
