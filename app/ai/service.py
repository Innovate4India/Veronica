"""Application-facing service for text-only AI responses."""

import re
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from app.ai.base import AIProvider, AIProviderError, ChatMessage
from app.ai.personality import VERONICA_SYSTEM_PROMPT
from app.ai.roles import (
    RoleDecision,
    VeronicaRole,
    classify_role,
    is_language_only_command,
    role_instructions,
    teaching_language_from_message,
)
from app.ai.teaching import TeachingSession
from app.ai.teacher_quality import (
    safe_teacher_response,
    teacher_quality_guidance,
    teacher_retry_instruction,
    validate_teacher_response,
)
from app.ai.tool_calling import (
    contains_tool_call_envelope,
    contains_web_search_tool_marker,
)
from app.config import MAX_CONVERSATION_MESSAGES
from app.memory import (
    MemoryService,
    MemoryServiceError,
    SensitiveMemoryError,
    detect_memory_intent,
)

_WEB_SEARCH_INSTRUCTIONS = """\
Web Search is available through the application's registered web_search tool.
Use it when the user needs current or external information; do not use it for
ordinary questions answerable without current web information. Only say you
searched or checked sources if the tool call succeeded. If it is unavailable
or fails, be transparent and do not invent search results.
The calculator tool is available for arithmetic. Use it for calculations
instead of estimating; pass only a mathematical expression.
The file_search tool is available for local filename and directory-name
searches. When the user asks to find, locate, or search for local files or
folders by name (including files related to a topic or project), call
file_search instead of asking them to provide an exact filename. Use a concise
query containing the distinguishing name/topic and project term. Omit its
optional path unless the user names a specific subdirectory; never pass an
empty path. It returns metadata only and never reads file contents. Never
claim to have opened or read a file based on file_search results.
The system_info tool provides read-only operating-system, CPU, memory,
Python-version, architecture, and project-drive capacity information. Use it
for questions about this computer's specifications or current resource usage.
It does not control the computer or expose credentials, environment variables,
usernames, or private paths.
The open_url tool requests opening a validated HTTP/HTTPS website in the
default browser only when the user explicitly asks to open or launch it. Use
web_search instead when the user asks for information about a website; do not
open sites merely to answer questions. Opening a page does not mean it loaded.
The tool does not inspect or interact with websites.
The screen_understanding tool captures one image of the primary display
locally, only when the user explicitly asks what is visible, asks you to look
at or describe the screen, identify an open application, or read visible text.
It sends the in-memory image only to the configured local Ollama vision model,
and returns the model's answer. Never claim or infer screen details unless
that tool succeeds. Do not use it for a general question unrelated to the
current screen.
The screenshot tool only captures locally and returns metadata; it cannot
interpret image contents. Do not call it to answer what is on screen when the
screen_understanding tool is available.
The app_launcher tool launches Notepad, Calculator, and Paint from fixed
Windows system targets, plus GUI applications discovered through current-user
and all-users Start Menu shortcuts or fixed known App Paths registrations (for
example Chrome, Edge, Firefox, Spotify, Discord, WhatsApp, VS Code, Word, or
Excel when safely registered and installed). Use it only when the user
explicitly asks to launch a desktop application by logical name. It never
accepts executable paths, arbitrary programs, scripts, shortcut arguments,
shell commands, or user-supplied process arguments. If matching is ambiguous,
ask the user to specify the application. Do not use it for websites (use
open_url) or computer-information questions (use system_info). It does not
control the application after launch.
Interpret an explicit request to open, launch, start, or run a GUI application
as an app_launcher request in English, Hindi, or Hinglish. For example,
'direct WhatsApp open karo', 'WhatsApp open karo', 'WhatsApp kholo',
'WhatsApp chalao', 'WhatsApp launch karo', 'Chrome kholo',
'Edge open kar do', 'Calculator kholo', and 'VS Code start karo' should call
app_launcher with application set only to the logical name ('WhatsApp',
'Chrome', 'Microsoft Edge', 'Calculator', or 'VS Code'). Words such as open,
khol, kholo, khol do, open karo, start karo, chalao, and launch karo express
the action; never include those words or the full user sentence in application.
Do not call app_launcher for informational questions such as 'What is
WhatsApp?', 'How does WhatsApp work?', 'Tell me about WhatsApp', or
'WhatsApp kya hai?'.
The application's current local date is {current_date}. Interpret "today,"
"latest," and "current" relative to this date; do not substitute another year.
For web_search, prefer omitting optional max_results (default 5). If provided,
it must be an unquoted integer from 1 through 8.
"""

_APP_NAME = (
    r"(?:notepad|calculator|paint|chrome|edge|firefox|spotify|discord|"
    r"whatsapp|vs\s*code|visual\s+studio\s+code|word|excel)"
)
_APP_ACTION = (
    r"(?:open(?:\s+kar(?:o|na))?|launch(?:\s+kar(?:o|na))?|"
    r"start(?:\s+kar(?:o|na))?|run|khol(?:o|na)?|chala(?:o|na)?(?:\s+do)?)"
)
_APP_LAUNCH_REQUEST = re.compile(
    rf"\b{_APP_ACTION}\b.*\b{_APP_NAME}\b|"
    rf"\b{_APP_NAME}\b.*\b{_APP_ACTION}\b",
    re.IGNORECASE,
)
_EXPLICIT_TOOL_REQUESTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "system_info",
        re.compile(
            r"\b(?:what(?:'s| is)\s+(?:my\s+)?(?:cpu|ram|memory|processor|"
            r"operating system|computer specs|system specs)|how much\s+"
            r"(?:ram|memory|storage)\s+do\s+i\s+have|"
            r"(?:computer|system)\s+(?:specifications|specs|info)|"
            r"(?:show|get|check)\s+(?:my\s+)?(?:computer|system)\s+"
            r"(?:specifications|specs|info))\b",
            re.IGNORECASE,
        ),
    ),
    ("app_launcher", _APP_LAUNCH_REQUEST),
    (
        "screen_understanding",
        re.compile(
            r"\b(?:what(?:'s| is)\s+(?:visible\s+)?(?:on|in)\s+my\s+screen|"
            r"look\s+at\s+(?:my\s+)?screen|describe\s+(?:my\s+)?screen|"
            r"read\s+(?:the\s+)?(?:text\s+)?on\s+(?:my\s+)?screen)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "screenshot",
        re.compile(
            r"\b(?:take|capture)\s+(?:a\s+)?(?:screenshot|screen\s*shot|"
            r"screen\s+capture|(?:my\s+)?screen)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "calculator",
        re.compile(
            r"\b(?:calculate|compute|work\s+out)\b(?=[^.!?]*\d)|"
            r"\b(?:what(?:'s| is)|how much)\s+[^.!?]*\d+\s*"
            r"(?:[+\-*/%]|\*\*)\s*[-\d(]",
            re.IGNORECASE,
        ),
    ),
    (
        "web_search",
        re.compile(
            r"\b(?:search|look\s+up)\b.*"
            r"\b(?:web|online|latest|current|news|internet)\b|"
            r"\b(?:what(?:'s| is)|tell me|show me)\b.*"
            r"\b(?:latest|current|recent|today'?s)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "file_search",
        re.compile(
            r"\b(?:find|locate|search\s+for)\b.*\b(?:file|files|folder|folders)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "open_url",
        re.compile(
            r"\b(?:open|go\s+to|visit)\b.*(?:https?://|www\.)",
            re.IGNORECASE,
        ),
    ),
)


class ToolCallingService(Protocol):
    """Minimal tool-calling boundary used by AIService when explicitly enabled."""

    def respond(
        self,
        messages: Sequence[ChatMessage],
        *,
        allowed_tool_names: frozenset[str] | None = None,
    ) -> str:
        """Return a final assistant answer after any tool round trips."""
        ...


class AIServiceError(Exception):
    """Raised when the AI service cannot return a response."""


class AIService:
    """Route user text to text-only AI or an explicitly injected tool service."""

    def __init__(
        self,
        provider: AIProvider,
        max_messages: int = MAX_CONVERSATION_MESSAGES,
        memory_service: MemoryService | None = None,
        tool_calling_service: ToolCallingService | None = None,
    ) -> None:
        if max_messages < 2:
            raise ValueError("max_messages must be at least 2.")
        self._provider = provider
        self._max_messages = max_messages
        self._memory_service = memory_service
        self._tool_calling_service = tool_calling_service
        self._role = VeronicaRole.ASSISTANT
        self._preferred_role = VeronicaRole.ASSISTANT
        self._teaching_session = TeachingSession()
        self._messages: list[ChatMessage] = [
            {"role": "system", "content": VERONICA_SYSTEM_PROMPT}
        ]

    def respond(self, user_message: str) -> str:
        """Return a model-generated response to a user message."""
        if not user_message.strip():
            raise ValueError("The user message must not be empty.")

        memory_intent = detect_memory_intent(user_message)
        if memory_intent.kind == "ambiguous":
            response = (
                "Do you want me to save a specific fact as a local memory? "
                "Please state exactly what you want me to remember."
            )
            self._record_exchange(user_message, response)
            return response
        if memory_intent.kind == "remember":
            if self._memory_service is None:
                response = "Persistent local memory is not available in this session."
                self._record_exchange(user_message, response)
                return response
            try:
                saved_memory = self._memory_service.save_memory(memory_intent.content)
            except SensitiveMemoryError:
                response = (
                    "I can’t store credentials or secrets as assistant memory. "
                    "Please keep passwords, keys, and tokens in a secure credential manager."
                )
                self._record_exchange(
                    "[An explicit memory request was refused because it appeared "
                    "to contain a credential or secret.]",
                    response,
                )
                return response
            except MemoryServiceError as error:
                raise AIServiceError("Local memory could not be saved.") from error
            response = f"I’ll remember this locally: {saved_memory.content}"
            self._record_exchange(user_message, response)
            return response

        language_preference = teaching_language_from_message(user_message)
        language_only_command = (
            language_preference is not None
            and is_language_only_command(user_message)
        )
        if language_preference is not None:
            self._teaching_session.set_language_preference(language_preference)
        if language_only_command:
            decision = RoleDecision(self._role)
        else:
            decision = self._classify_current_turn(user_message)
            self._role = decision.role
            self._preferred_role = decision.role
            self._teaching_session.apply_decision(decision, role=self._role)
        retrieved_memories = []
        explicitly_requested_tools = _explicit_tool_names(user_message)
        if self._memory_service is not None:
            try:
                retrieved_memories = self._memory_service.search_memories(user_message)
            except MemoryServiceError as error:
                raise AIServiceError("Local memories could not be retrieved.") from error

        system_content = VERONICA_SYSTEM_PROMPT
        use_tools = (
            self._tool_calling_service is not None
            and bool(explicitly_requested_tools)
        )
        if use_tools:
            system_content += "\n\n" + _WEB_SEARCH_INSTRUCTIONS.format(
                current_date=date.today().isoformat()
            )
            system_content += (
                "\nFor this turn, only use these separately requested "
                "capabilities if needed: "
                + ", ".join(sorted(explicitly_requested_tools))
                + ". Do not use other tools."
            )
        system_content += "\n\n" + role_instructions(
            self._role,
            self._teaching_session.prompt_context(),
        )
        if self._role is VeronicaRole.TEACHER and not use_tools:
            system_content += teacher_quality_guidance()
        if retrieved_memories:
            memory_lines = [
                f"- [{memory.category}] {memory.content}"
                for memory in retrieved_memories
            ]
            system_content += (
                "\n\nRelevant user memories retrieved from the local database:\n"
                + "\n".join(memory_lines)
            )
        messages = [
            {"role": "system", "content": system_content},
            *self._messages[1:],
            {"role": "user", "content": user_message},
        ]
        try:
            if not use_tools:
                response = self._provider.generate_response(messages)
            else:
                assert self._tool_calling_service is not None
                response = self._tool_calling_service.respond(
                    messages,
                    allowed_tool_names=explicitly_requested_tools,
                )
        except AIProviderError as error:
            raise AIServiceError("The local AI provider could not respond.") from error

        if self._role is VeronicaRole.TEACHER and not use_tools:
            candidate = response if isinstance(response, str) else ""
            validation = validate_teacher_response(
                user_message,
                candidate,
                self._teaching_session.language_preference,
            )
            if not validation.is_valid:
                retry_messages: list[ChatMessage] = [
                    {"role": message["role"], "content": message["content"]}
                    for message in messages
                ]
                retry_messages[0]["content"] += (
                    "\n\n"
                    + teacher_retry_instruction(
                        validation,
                        self._teaching_session.language_preference,
                        user_message,
                    )
                )
                try:
                    retry_response = self._provider.generate_response(
                        retry_messages
                    )
                except AIProviderError:
                    retry_response = ""
                retry_candidate = (
                    retry_response if isinstance(retry_response, str) else ""
                )
                retry_validation = validate_teacher_response(
                    user_message,
                    retry_candidate,
                    self._teaching_session.language_preference,
                )
                if retry_validation.is_valid:
                    response = retry_candidate
                else:
                    response = safe_teacher_response(
                        self._teaching_session.language_preference,
                        user_message,
                    )

        if not isinstance(response, str) or not response.strip():
            raise AIServiceError("The local AI provider returned no assistant text.")
        if (
            not use_tools
            and contains_web_search_tool_marker(response)
        ):
            raise AIServiceError(
                "Web Search is disabled; enable WEB_SEARCH_ENABLED to use it."
            )
        if contains_tool_call_envelope(response):
            raise AIServiceError(
                "The model returned a tool-call envelope as text; no tool was executed."
            )

        response = response.strip()
        if (
            use_tools
            and getattr(
                self._tool_calling_service,
                "last_turn_used_screen_understanding",
                False,
            )
            is True
        ):
            self._record_exchange(
                user_message,
                "[Screen-understanding response omitted from conversation history.]",
            )
        else:
            self._record_exchange(user_message, response)
        if self._role is VeronicaRole.TEACHER:
            self._teaching_session.record_assistant_response(response)
        return response

    def _classify_current_turn(self, user_message: str) -> RoleDecision:
        return classify_role(
            self._provider,
            user_message,
            self._messages[1:],
            preferred_role=self._preferred_role,
            teaching_context=self._teaching_session.prompt_context(),
        )

    def _record_exchange(self, user_message: str, response: str) -> None:
        self._messages.extend(
            [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": response},
            ]
        )
        while len(self._messages) - 1 > self._max_messages:
            del self._messages[1:3]

    @property
    def messages(self) -> tuple[ChatMessage, ...]:
        """Return the current conversation, including its system prompt."""
        return tuple(
            {"role": message["role"], "content": message["content"]}
            for message in self._messages
        )

    @property
    def message_count(self) -> int:
        """Return the number of current conversation messages."""
        return len(self._messages)

    def clear(self) -> None:
        """Clear session history while keeping Veronica's system prompt."""
        self._messages[:] = [
            {"role": "system", "content": VERONICA_SYSTEM_PROMPT}
        ]
        self._role = VeronicaRole.ASSISTANT
        self._preferred_role = VeronicaRole.ASSISTANT
        self._teaching_session.request_reset()

    @property
    def role(self) -> VeronicaRole:
        """The role selected for the most recently handled turn."""
        return self._role

    @property
    def teaching_session(self) -> TeachingSession:
        """Session-local teaching progress; never stored in persistent memory."""
        return self._teaching_session


def _explicit_tool_names(message: str) -> frozenset[str]:
    return frozenset(
        name
        for name, pattern in _EXPLICIT_TOOL_REQUESTS
        if pattern.search(message) is not None
    )
