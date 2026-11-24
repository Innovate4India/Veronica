"""Safe interactive developer interface for the local Ollama model."""

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from app.ai import (
    AIService,
    AIServiceError,
    OllamaClient,
    OllamaConfigurationError,
    OllamaConnectionError,
    OllamaResponseError,
    OllamaTimeoutError,
    OllamaToolCallingService,
)
from app.ai.vision import LocalVisionService
from app.config import (
    MAX_RELEVANT_MEMORIES,
    MEMORY_DATABASE_PATH,
    WebSearchConfig,
    load_file_search_roots,
    load_ollama_config,
    load_ollama_vision_model,
    load_spoken_response_config,
    load_web_search_config,
    load_web_search_enabled,
)
from app.memory import (
    Memory,
    MemoryService,
    MemoryServiceError,
    SensitiveMemoryError,
    detect_memory_intent,
)
from app.voice import TextToSpeechProvider, VoiceError
from app.voice.microsoft_tts import MicrosoftNeuralTTS
from app.tools import (
    AppLauncherTool,
    CalculatorTool,
    FileSearchTool,
    OpenURLTool,
    ScreenshotTool,
    ScreenUnderstandingTool,
    SystemInfoTool,
    ToolRegistry,
    WebSearchTool,
)


OLLAMA_UNAVAILABLE_MESSAGE = (
    "Veronica cannot reach the local AI engine. "
    "Please make sure Ollama is running."
)


def _create_tool_registry(
    web_search_config: WebSearchConfig,
    file_search_roots: tuple[Path, ...],
    ollama_client: OllamaClient,
) -> ToolRegistry:
    tool_registry = ToolRegistry()
    tool_registry.register(WebSearchTool(config=web_search_config))
    tool_registry.register(CalculatorTool())
    tool_registry.register(FileSearchTool(file_search_roots))
    tool_registry.register(SystemInfoTool())
    tool_registry.register(OpenURLTool())
    tool_registry.register(AppLauncherTool())
    tool_registry.register(ScreenshotTool())
    tool_registry.register(
        ScreenUnderstandingTool(
            LocalVisionService(
                client=ollama_client,
                model=load_ollama_vision_model(),
            )
        )
    )
    return tool_registry


@dataclass
class _CommandState:
    pending_memory_clear: bool = False


def _speak_assistant_response(
    response: str,
    provider: TextToSpeechProvider,
    language: str,
) -> None:
    try:
        provider.speak(response, language=language)
    except VoiceError as error:
        print(f"Spoken response unavailable: {error}", file=sys.stderr)
    except Exception as error:
        print(
            f"Spoken response failed ({type(error).__name__}): {error}",
            file=sys.stderr,
        )


def _print_help() -> None:
    print(
        "Available commands:\n"
        "  /exit    Exit Veronica\n"
        "  /clear   Clear conversation history\n"
        "  /history Show the number of conversation messages\n"
        "  /remember <text>  Save an explicitly approved local memory\n"
        "  /memory  List stored local memories\n"
        "  /forget <id>  Delete one local memory\n"
        "  /memory-search <query>  Search local memories\n"
        "  /clear-memory  Request confirmation to delete all local memories\n"
        "  /help    Show this help message"
    )


def _print_memories(memories: list[Memory]) -> None:
    if not memories:
        print("No matching memories found.")
        return
    for memory in memories:
        print(f"[{memory.id}] ({memory.category}) {memory.content}")


def _handle_command(
    command: str,
    service: AIService,
    memory_service: MemoryService,
    state: _CommandState,
) -> bool:
    """Handle an application command; return True when the session should exit."""
    normalized = command.strip()
    lowered = normalized.lower()
    if lowered == "/exit":
        print("Goodbye.")
        return True
    if lowered == "/clear":
        service.clear()
        print("Conversation cleared.")
    elif lowered == "/history":
        print(
            f"Conversation messages: {service.message_count} "
            "(including system prompt)."
        )
    elif lowered == "/help":
        _print_help()
    elif lowered == "/memory":
        _print_memories(memory_service.list_memories())
    elif lowered == "/remember" or lowered.startswith("/remember "):
        _, separator, content = normalized.partition(" ")
        if not separator or not content.strip():
            print("Usage: /remember <text>")
        else:
            try:
                memory = memory_service.save_memory(content)
            except SensitiveMemoryError as error:
                print(str(error))
            else:
                print(f"Saved local memory [{memory.id}].")
    elif lowered == "/forget" or lowered.startswith("/forget "):
        _, separator, memory_id_text = normalized.partition(" ")
        if not separator or not memory_id_text.strip():
            print("Usage: /forget <id>")
        else:
            try:
                memory_id = int(memory_id_text.strip())
            except ValueError:
                print("Memory ID must be a positive integer.")
            else:
                if memory_service.delete_memory(memory_id):
                    print(f"Deleted local memory [{memory_id}].")
                else:
                    print(f"No local memory found with ID [{memory_id}].")
    elif lowered == "/memory-search" or lowered.startswith("/memory-search "):
        _, separator, query = normalized.partition(" ")
        if not separator or not query.strip():
            print("Usage: /memory-search <query>")
        else:
            _print_memories(memory_service.search_memories(query))
    elif lowered == "/clear-memory":
        state.pending_memory_clear = True
        print(
            "This will permanently delete all local memories. "
            "Type YES on the next prompt to confirm; any other response cancels."
        )
    else:
        print(f"Unknown command: {command}. Type /help to see available commands.")
    return False


def _confirm_memory_clear(
    confirmation: str,
    memory_service: MemoryService,
    state: _CommandState,
) -> None:
    state.pending_memory_clear = False
    if confirmation.strip().casefold() != "yes":
        print("Memory deletion cancelled.")
        return
    deleted_count = memory_service.clear_all_memories()
    print(f"Deleted {deleted_count} local memor{'y' if deleted_count == 1 else 'ies'}.")


def main() -> int:
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")

    try:
        config = load_ollama_config()
    except ValueError as error:
        print(f"Ollama configuration error: {error}")
        return 2
    try:
        spoken_response_config = load_spoken_response_config()
    except ValueError as error:
        print(f"Spoken response configuration error: {error}")
        return 2
    try:
        web_search_enabled = load_web_search_enabled()
    except ValueError as error:
        print(f"Web search configuration error: {error}")
        return 2
    if not config.model:
        print(
            "OLLAMA_MODEL is not configured. Choose and install a model explicitly, "
            "then set OLLAMA_MODEL to its name. For example:\n"
            "  ollama pull llama3.2\n"
            '  $env:OLLAMA_MODEL = "llama3.2"'
        )
        return 2

    try:
        client = OllamaClient(config)
        available_models = client.list_models()
    except OllamaConfigurationError as error:
        print(f"Ollama configuration error: {error}")
        return 2
    except OllamaTimeoutError:
        print(OLLAMA_UNAVAILABLE_MESSAGE)
        return 1
    except OllamaConnectionError:
        print(OLLAMA_UNAVAILABLE_MESSAGE)
        return 1
    except OllamaResponseError as error:
        print(f"The local Ollama service returned an invalid response: {error}")
        return 1

    expected_names = {config.model}
    if ":" not in config.model:
        expected_names.add(f"{config.model}:latest")
    if not expected_names.intersection(available_models):
        print(f"Configured model {config.model!r} is not installed locally.")
        print(f"Install it explicitly with: ollama pull {config.model}")
        return 2

    try:
        memory_service = MemoryService(
            MEMORY_DATABASE_PATH,
            MAX_RELEVANT_MEMORIES,
        )
    except (OSError, sqlite3.Error) as error:
        print(f"Could not initialize local memory database: {error}")
        return 1

    tool_calling_service = None
    if web_search_enabled:
        try:
            web_search_config = load_web_search_config()
        except ValueError as error:
            print(f"Web search configuration error: {error}")
            return 2
        try:
            file_search_roots = load_file_search_roots()
        except ValueError as error:
            print(f"File search configuration error: {error}")
            return 2
        tool_registry = _create_tool_registry(
            web_search_config,
            file_search_roots,
            client,
        )
        tool_calling_service = OllamaToolCallingService(client, tool_registry)
    service = AIService(
        client,
        memory_service=memory_service,
        tool_calling_service=tool_calling_service,
    )
    speech_provider = (
        MicrosoftNeuralTTS(spoken_response_config)
        if spoken_response_config.enabled
        else None
    )
    command_state = _CommandState()
    print(
        "========================================\n"
        "           VERONICA AI\n"
        "     Local Personal Assistant\n"
        "========================================\n"
        "\nType /exit to quit.\n"
        "Type /clear to clear conversation.\n"
        "Type /history to show the number of messages in the current session.\n"
        "Use /remember, /memory, /forget, /memory-search, or /clear-memory "
        "for local memory.\n"
        "Type /help to display available commands.\n"
    )
    while True:
        try:
            user_message = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_message:
            continue
        if command_state.pending_memory_clear:
            try:
                _confirm_memory_clear(user_message, memory_service, command_state)
            except MemoryServiceError as error:
                print(f"Could not clear local memories: {error}", file=sys.stderr)
            if user_message.casefold() == "/exit":
                print("Goodbye.")
                return 0
            continue
        if user_message.startswith("/"):
            try:
                if _handle_command(
                    user_message,
                    service,
                    memory_service,
                    command_state,
                ):
                    return 0
            except MemoryServiceError as error:
                print(f"Local memory operation failed: {error}", file=sys.stderr)
            continue
        try:
            response = service.respond(user_message)
            print(f"Veronica: {response}")
            if (
                speech_provider is not None
                and detect_memory_intent(user_message).kind == "none"
            ):
                _speak_assistant_response(
                    response,
                    speech_provider,
                    spoken_response_config.language,
                )
        except AIServiceError as error:
            if isinstance(error.__cause__, OllamaConnectionError):
                print(OLLAMA_UNAVAILABLE_MESSAGE, file=sys.stderr)
            else:
                print(f"Veronica could not respond: {error}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
