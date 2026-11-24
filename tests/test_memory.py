"""Tests for local persistent memory and natural-language memory requests."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app.ai import AIProvider, AIService
from app.ai.personality import VERONICA_SYSTEM_PROMPT
from app.memory import (
    MemoryDatabase,
    MemoryService,
    MemoryServiceError,
    SensitiveMemoryError,
    detect_memory_intent,
)


class MemoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "nested" / "veronica_memory.db"
        )
        self.service = MemoryService(self.database_path)

    def test_database_and_nested_directory_are_created(self) -> None:
        self.assertTrue(self.database_path.is_file())
        self.assertTrue(self.database_path.parent.is_dir())
        self.assertEqual(self.service.list_memories(), [])

    def test_saves_memory_with_sqlite_timestamps(self) -> None:
        memory = self.service.save_memory("I am learning Python.", "learning")

        self.assertEqual(memory.id, 1)
        self.assertEqual(memory.content, "I am learning Python.")
        self.assertEqual(memory.category, "learning")
        self.assertTrue(memory.created_at)
        self.assertEqual(memory.created_at, memory.updated_at)

    def test_lists_memories_newest_first(self) -> None:
        first = self.service.save_memory("My main project is Veronica.")
        second = self.service.save_memory("I use Python.")

        self.assertEqual(
            [memory.id for memory in self.service.list_memories()],
            [second.id, first.id],
        )

    def test_searches_relevant_memories_and_obeys_limit(self) -> None:
        self.service = MemoryService(self.database_path, max_relevant_memories=2)
        self.service.save_memory("I use Python for scripting.")
        self.service.save_memory("I am learning Python basics.")
        newest = self.service.save_memory("I am learning Python every day.")
        unrelated = self.service.save_memory("My favorite color is blue.")

        results = self.service.search_memories("What am I learning?")

        second_newest = self.service.list_memories()[2]
        self.assertEqual(len(results), 2)
        self.assertEqual(
            [memory.id for memory in results],
            [newest.id, second_newest.id],
        )
        self.assertNotIn(
            "My favorite color is blue.",
            [memory.content for memory in results],
        )
        self.assertEqual(unrelated.content, "My favorite color is blue.")

    def test_search_query_is_parameterized(self) -> None:
        malicious_text = "Python%' OR 1=1; DROP TABLE memories; --"
        stored = self.service.save_memory(malicious_text)

        results = self.service.search_memories(malicious_text)
        self.assertEqual([memory.id for memory in results], [stored.id])
        self.assertEqual(len(self.service.list_memories()), 1)

    def test_delete_memory_reports_missing_and_existing_ids(self) -> None:
        memory = self.service.save_memory("My main project is Veronica.")

        self.assertFalse(self.service.delete_memory(memory.id + 100))
        self.assertTrue(self.service.delete_memory(memory.id))
        self.assertEqual(self.service.list_memories(), [])

    def test_clear_all_memories_returns_deleted_count(self) -> None:
        self.service.save_memory("First memory.")
        self.service.save_memory("Second memory.")

        self.assertEqual(self.service.clear_all_memories(), 2)
        self.assertEqual(self.service.list_memories(), [])

    def test_empty_database_returns_no_search_results(self) -> None:
        self.assertEqual(self.service.search_memories("Python"), [])
        self.assertEqual(self.service.search_memories("What am I learning?"), [])

    def test_empty_or_invalid_values_are_rejected(self) -> None:
        for content, category in (("", "general"), (" ", "general"), ("Fact", " ")):
            with self.subTest(content=content, category=category):
                with self.assertRaises(ValueError):
                    self.service.save_memory(content, category)
        with self.assertRaises(ValueError):
            self.service.delete_memory(0)

    def test_obvious_credentials_are_never_persisted(self) -> None:
        secret_values = (
            "My password is hunter2.",
            "The API key: sk-example-secret",
            "Remember my token is abcdefgh123456.",
            "Use bearer abcdefgh123456.",
            "-----BEGIN PRIVATE KEY-----",
        )
        for secret in secret_values:
            with self.subTest(secret=secret):
                with self.assertRaises(SensitiveMemoryError):
                    self.service.save_memory(secret)
        self.assertEqual(self.service.list_memories(), [])

    def test_sqlite_errors_are_reported_without_memory_content(self) -> None:
        database = MemoryDatabase(self.database_path)
        with database.connection() as connection:
            connection.execute("DROP TABLE memories")
        service = MemoryService(database=database)

        with self.assertRaisesRegex(MemoryServiceError, "Could not list"):
            service.list_memories()


class MemoryIntentTests(unittest.TestCase):
    def test_recognizes_clear_explicit_memory_requests(self) -> None:
        requests = (
            (
                "Remember that my main project is Veronica.",
                "my main project is Veronica",
            ),
            (
                "I want you to remember that I use Python.",
                "I use Python",
            ),
            (
                "Please remember my preferred programming language is Python.",
                "my preferred programming language is Python",
            ),
        )
        for message, expected_content in requests:
            with self.subTest(message=message):
                intent = detect_memory_intent(message)
                self.assertEqual(intent.kind, "remember")
                self.assertEqual(intent.content, expected_content)

    def test_asks_for_clarification_on_incomplete_or_ambiguous_request(self) -> None:
        for message in ("Remember", "Please remember that", "Remember Python?"):
            with self.subTest(message=message):
                self.assertEqual(detect_memory_intent(message).kind, "ambiguous")
        self.assertEqual(detect_memory_intent("I use Python.").kind, "none")

    def test_explicit_natural_language_request_saves_without_calling_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(Path(temporary_directory) / "memory.db")
            provider = Mock(spec=AIProvider)
            service = AIService(provider, memory_service=memory_service)

            response = service.respond("Remember that I am learning Python.")

            self.assertIn("remember this locally", response.lower())
            self.assertEqual(
                memory_service.list_memories()[0].content,
                "I am learning Python",
            )
            provider.generate_response.assert_not_called()

    def test_ambiguous_request_does_not_save_or_call_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(Path(temporary_directory) / "memory.db")
            provider = Mock(spec=AIProvider)
            service = AIService(provider, memory_service=memory_service)

            response = service.respond("Remember?")

            self.assertIn("specific fact", response)
            self.assertEqual(memory_service.list_memories(), [])
            provider.generate_response.assert_not_called()

    def test_natural_secret_request_is_refused_without_persistence_or_llm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(Path(temporary_directory) / "memory.db")
            provider = Mock(spec=AIProvider)
            service = AIService(provider, memory_service=memory_service)

            response = service.respond("Remember that my password is hunter2.")

            self.assertIn("can’t store credentials", response)
            self.assertEqual(memory_service.list_memories(), [])
            provider.generate_response.assert_not_called()

    def test_refused_secret_is_not_forwarded_in_later_conversation_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(Path(temporary_directory) / "memory.db")
            provider = Mock(spec=AIProvider)
            provider.generate_response.return_value = "I can help with general questions."
            service = AIService(provider, memory_service=memory_service)

            service.respond("Remember that my password is hunter2.")
            service.respond("Can you help me?")

            request_messages = provider.generate_response.call_args.args[0]
            self.assertNotIn(
                "hunter2",
                "\n".join(message["content"] for message in request_messages),
            )

    def test_retrieves_only_limited_matching_memories_for_local_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(
                Path(temporary_directory) / "memory.db",
                max_relevant_memories=1,
            )
            memory_service.save_memory("I am learning Python.")
            memory_service.save_memory("I am learning SQL.")
            provider = Mock(spec=AIProvider)
            provider.generate_response.return_value = "You are learning SQL."
            service = AIService(provider, memory_service=memory_service)

            service.respond("What am I learning?")

            request_messages = provider.generate_response.call_args.args[0]
            self.assertEqual(len(request_messages), 2)
            system_content = request_messages[0]["content"]
            self.assertIn("Relevant user memories retrieved", system_content)
            self.assertIn("I am learning SQL.", system_content)
            self.assertNotIn("I am learning Python.", system_content)
            self.assertIn("Veronica", VERONICA_SYSTEM_PROMPT)

    def test_omits_memory_context_when_nothing_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            memory_service = MemoryService(Path(temporary_directory) / "memory.db")
            memory_service.save_memory("My main project is Veronica.")
            provider = Mock(spec=AIProvider)
            provider.generate_response.return_value = "The weather is sunny."
            service = AIService(provider, memory_service=memory_service)

            service.respond("What is the weather?")

            system_content = provider.generate_response.call_args.args[0][0]["content"]
            self.assertNotIn("Relevant user memories", system_content)


if __name__ == "__main__":
    unittest.main()
