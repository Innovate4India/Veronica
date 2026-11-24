# Veronica

Veronica is a local-first assistant. Its conversational AI uses a local Ollama
server, and explicit user-approved memories are stored in a local SQLite
database. No cloud LLM provider, always-listening voice, computer control,
browser automation, file modification, or authentication is exposed to users.
Explicitly requested tools are bounded and described below. Optional online
Microsoft Neural TTS is described below.

Phase 5 includes a local faster-whisper STT provider and a safe diagnostic
command. The default model is `base`, expected at
`data/models/whisper/base`; configure `WHISPER_MODEL`,
`WHISPER_MODEL_PATH`, `WHISPER_DEVICE`, and `WHISPER_COMPUTE_TYPE` in the
process environment. `WHISPER_MODEL_PATH` accepts `{model}` as a placeholder.
No model is downloaded by the application. Put a compatible CTranslate2
Whisper model (including `model.bin` and `config.json`) at that path before
using speech recognition.

Run `python -m app.voice.diagnostic` to check the configured model and list
audio input devices. This is read-only and does not record audio. Microphone
capture is only initiated by an explicit call to the STT provider's `listen()`.
The existing voice orchestration/provider interfaces are not wired into
`dev_ai.py`. Realtek/WASAPI microphone device 11 has been tested successfully
with a local transcription.

For an explicit one-shot real microphone test, run
`python -m app.voice.microphone_test`. It lists Realtek input devices, selects
the first device whose name identifies it as a Realtek microphone, asks for
Enter before recording once for 5 seconds, then prints the local transcription.
To select a device from the listed sounddevice indices, pass
`--device-index <index>`; an alternate bounded duration may be provided with
`--duration 5` through `--duration 10`. Audio is held in memory only and is not
saved.

Spoken CLI replies now use Microsoft Edge's online Neural TTS through the
`edge-tts` package. This is **not offline**: eligible assistant response text is
sent to Microsoft's online speech service when `VOICE_RESPONSES_ENABLED=true`.
Spoken replies remain disabled by default. No microphone is activated and no
audio file is written. The existing local Piper provider and diagnostic remain
available, but the conversational loop does not route through Piper.

Veronica defaults to `hi-IN-SwaraNeural` for **both Hindi and English**, so
language selection cannot silently switch the assistant to a male voice. The
application validates voice settings against an allowlist of Microsoft-listed
female voices; invalid or male voice names are rejected. The common starting
prosody is `MICROSOFT_TTS_RATE=-10%`, `MICROSOFT_TTS_PITCH=+0Hz`, and
`MICROSOFT_TTS_VOLUME=+0%`.

To audition the exact requested phrases through the default Windows audio
output, run:

```powershell
python -m app.voice.microsoft_tts_test --language hi
python -m app.voice.microsoft_tts_test --language en
```

Both use `hi-IN-SwaraNeural` by default. The diagnostic reports the selected
voice, rate/pitch/volume, sample rate, sample count, duration, and playback
result. It needs an internet connection, holds audio in memory, and does not
save audio. Actual English pronunciation quality is subjective; listen to the
English sample before deciding whether Swara is acceptable for technical terms.

If Swara's English is not acceptable, Microsoft's documented female Indian
English voices include `en-IN-NeerjaNeural`, `en-IN-KavyaNeural`, and
`en-IN-AnanyaNeural`. Audition a candidate without changing production settings,
for example:

```powershell
python -m app.voice.microsoft_tts_test --language en --voice en-IN-NeerjaNeural
```

If selected after listening, set
`MICROSOFT_TTS_ENGLISH_VOICE=en-IN-NeerjaNeural`; it remains female and uses
the same rate, pitch, and volume as Hindi. The application cannot decide whether
accent/pronunciation sounds acceptable on your speakers, so this is not
automatically selected as a fallback.

Enable English spoken replies in PowerShell with:

```powershell
$env:VOICE_RESPONSES_ENABLED = "true"
$env:VOICE_RESPONSE_LANGUAGE = "en"
python dev_ai.py
```

Set `VOICE_RESPONSE_LANGUAGE=hi` for Hindi. Configure
`MICROSOFT_TTS_HINDI_VOICE`, `MICROSOFT_TTS_ENGLISH_VOICE`,
`MICROSOFT_TTS_RATE`, `MICROSOFT_TTS_PITCH`, and `MICROSOFT_TTS_VOLUME` in the
environment. Only ordinary assistant replies are spoken; commands, memory
operations, and errors remain text-only. Speech/network failures are reported
without interrupting the text conversation, and synthesis/playback are bounded.

Microsoft's [official Azure Speech voice list](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts)
identifies `hi-IN-SwaraNeural` as Female and lists the alternative Indian
English voices above as Female. Veronica uses the Edge online TTS endpoint via
the `edge-tts` package (not Azure Speech REST, which requires an Azure resource
key).

The local Piper installation is retained. Its configured files are
`data/models/piper/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx` and
`data/models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx`, each with its
matching `.onnx.json` sidecar. Its independent diagnostic remains available:

```powershell
python -m app.voice.tts_test --language hi
python -m app.voice.tts_test --language en
```

To troubleshoot Windows/sounddevice capture independently of Whisper, run
`python -m app.voice.microphone_capture_diagnostic`. It lists all input devices,
shows the default input, checks mono float32 at the selected device's default
sample rate, then asks before capturing about 2 seconds. It reports signal
statistics and sounddevice exception details; audio remains in memory only.
Use `--device-index <index>` to select an input device explicitly.

The Ollama client uses only Python's standard library. Configure the process
environment using the values in `.env.example` (the example file is not loaded
automatically), and set `OLLAMA_MODEL` to a model already installed in Ollama.
For example, after explicitly choosing a model:

```powershell
ollama pull llama3.2
$env:OLLAMA_MODEL = "llama3.2"
python dev_ai.py
```

`dev_ai.py` checks the local service and configured model before starting an
interactive conversation as Veronica. Session conversation history is kept
in memory and is bounded by `MAX_CONVERSATION_MESSAGES` (20 non-system
messages by default); `/clear` resets it without removing Veronica's system
instructions.

## Veronica Companion & Teacher — Step 1

Veronica can respond in three conversational roles while keeping the same
identity:

- **Friend** for casual conversation, personal sharing, and hobbies.
- **Teacher** for learning concepts, coding, academic topics, English practice,
  and quizzes. Veronica can explain with examples, give hints, check practice
  answers, and adjust the lesson difficulty gradually.
- **Assistant** for general questions and supported application tasks.

Role selection follows the user's current intent; an explicit mode request can
also be used, such as `Friend mode`, `Teacher mode`, `Assistant mode`, or
`Quiz me on Python`. A prior role does not prevent switching when the user asks
for something different.

Teaching progress is held in memory for the current process only. It can track
the active subject/topic, approximate level, quiz and question state, and
answer progress to guide the current lesson. It is not added to SQLite memory
and is reset when the conversation is cleared or the application exits.
Veronica is still a conversational assistant: mouse/keyboard control,
clicking, typing, and autonomous computer control are not part of this step.

Manual checks:

1. Start casually (for example, `I had a relaxing weekend`) and confirm
   Veronica responds conversationally without forcing a lesson.
2. Ask `Teach me Python loops` or `Quiz me on Python`, answer a question, and
   confirm she stays in a learning flow and responds to the answer.
3. Switch to `Friend mode` or `Assistant mode` and confirm her behavior changes
   without changing Veronica's identity.
4. Use `/clear` and verify the session's lesson progress is reset.

## Tool-calling architecture

`app.tools` defines an isolated extension point for future tool execution:
subclass `Tool` to provide a stable name, description, object parameter schema,
and `execute()` implementation, then explicitly add it to an instance of
`ToolRegistry`. The registry rejects duplicate registrations, validates
parameters against its supported schema subset, and returns a structured
`ToolResult` status (`success`, `validation_failure`, `execution_failure`,
`timeout`, `unavailable`, or `permission_required`). A tool can declare
`requires_confirmation=True`, in which case the registry refuses execution
unless dispatch explicitly supplies `confirmed=True`. Registry instances do not
share registrations. Importing the tool package does not register tools.

`app.tools.web_search.WebSearchTool` implements a read-only search adapter
using the documented Tavily Search API (`POST https://api.tavily.com/search`).
It returns only bounded titles, result URLs, and short snippets; it never
fetches result pages. The provider is selected with `WEB_SEARCH_PROVIDER`
(`tavily`, the default), configured with `TAVILY_API_KEY`, and uses
`WEB_SEARCH_TIMEOUT_SECONDS` (1–20 seconds; default 8). The endpoint is fixed
to Tavily's official API and is not configurable. Create a key through
[Tavily](https://app.tavily.com), then set it in the process environment, for
example in PowerShell:

```powershell
$env:WEB_SEARCH_ENABLED = "true"
$env:WEB_SEARCH_PROVIDER = "tavily"
$env:TAVILY_API_KEY = "<your-tavily-api-key>"
$env:WEB_SEARCH_TIMEOUT_SECONDS = "8"
$env:VERONICA_FILE_SEARCH_ROOTS = "D:\veronica;D:\projects"
```

Web Search is opt-in and defaults to disabled. Set
`WEB_SEARCH_ENABLED=true` and configure `TAVILY_API_KEY` to enable it. While
disabled, the ordinary text-only Ollama request path is used: Ollama receives
no tool definitions, the Tavily configuration is not loaded, and no web
request can occur. When enabled, the application creates a session-local
`ToolRegistry`, registers `WebSearchTool`, `CalculatorTool`, `FileSearchTool`,
`SystemInfoTool`, `OpenURLTool`, and `AppLauncherTool`, and provides that registry to
`OllamaToolCallingService`.
Ollama decides whether to call a tool; there
is no keyword-based routing. Only the search query and bounded result count
are sent to Tavily, never the conversation history. Search queries leave the
local machine and are processed by Tavily. Missing credentials or provider
failures are returned to Ollama as structured tool outcomes so Veronica can
respond honestly. Tool results are used for that response and are not written
to SQLite memory.

`FileSearchTool` is read-only and searches filenames and directory names only;
it does not read or return file contents, open files, or send filesystem
information to Tavily. It is limited to `VERONICA_FILE_SEARCH_ROOTS`, a
semicolon-separated list of absolute Windows paths. The default is only the
Veronica project directory. For example, set
`$env:VERONICA_FILE_SEARCH_ROOTS = "D:\veronica;D:\projects"` to permit search
in those two roots. Requested subpaths must resolve inside a configured root.
Parent traversal, symbolic links/reparse points, common credential names and
locations, and common large dependency directories are excluded. Searches
have a 2-second runtime limit, visit at most 10,000 entries, and return at
most 50 results. File search is available only when the existing tool-enabled
conversation path is active (`WEB_SEARCH_ENABLED=true`).

`SystemInfoTool` is also available in that tool-enabled conversation path. It
is local-only, read-only, and requires no API key or additional configuration.
It returns only bounded OS, CPU, RAM, Python, architecture, and Veronica
project-drive capacity metrics; it does not expose usernames, environment
variables, private paths, credentials, or browser information. A metric that
cannot be retrieved is marked unavailable rather than preventing the other
requested metrics from being returned.

`OpenURLTool` requires no API key or configuration. When the user explicitly
asks Veronica to open or launch a website, it validates an HTTP/HTTPS URL and
asks Python's `webbrowser` module to open it in the default browser. Plain
public domains such as `github.com` are normalized to HTTPS. The tool does not
make a network request itself and cannot tell whether a page finished loading.
It does not inspect or interact with the page, download content, run scripts,
or access browser accounts/data. Website information requests remain distinct
and should use normal answers or Web Search, not URL opening.

`AppLauncherTool` is available in the same tool-enabled conversation path and
requires no API key or additional configuration. Notepad, Calculator, and
Paint use fixed executable names from the Windows system directory. Other
applications are discovered from shortcuts under the current-user and
all-users Windows Start Menu `Programs` locations and from read-only App Paths
registrations for a fixed set of known GUI executable names. App Paths checks
only those named registry entries in the current-user and machine registry
views; no registry-wide enumeration, whole-drive scan, PATH lookup, or
user-selected directory is used. This can discover installed GUI applications
such as Chrome, Edge, Firefox, Spotify, Discord, WhatsApp, VS Code, Word, and
Excel when their registrations and installed targets meet the validation
checks. Selected known Microsoft Store package identities (including WhatsApp,
Calculator, Paint, Photos, and Spotify) are read from the current user's
registered package metadata as discovery-only entries. They have no executable
target and are reported unavailable; package activation is not implemented.

Shortcuts and App Paths entries must resolve to an existing `.exe` inside a
known application installation directory. Shortcuts with any arguments and
registry entries with arguments, a mismatched executable identity, or an
untrusted target are rejected, as are non-executable targets, URLs, missing
targets, reparse-point paths, scripts, installers, and known command
interpreters. Store package identities are never treated as executable paths
and cannot be launched by this tool. Duplicate registrations for the same
normalized name and validated target are merged; distinct targets remain
separate so ambiguous names are not guessed. Discovery has strict entry and
shortcut/package limits.
Matching is exact after normalization or through explicit aliases
(for example `chrome`/`google chrome`, `edge`/`microsoft edge`,
`firefox`/`mozilla firefox`, `spotify`, `discord`,
`whatsapp`/`whatsapp desktop`, `vscode`/`vs code`/`visual studio code`/`code`,
`word`/`microsoft word`, and `excel`/`microsoft excel`). If multiple targets match, Veronica
does not guess. Launching uses one validated executable and
`subprocess.Popen(..., shell=False)` with no arguments. No arbitrary `.exe`
paths, commands, scripts, installations, elevation, or process control are
supported; arbitrary executable launch is intentionally forbidden. Store
package discovery is metadata-only; package identity strings and manifest
paths are not executable targets, and no shell-based AppsFolder/URI fallback
is used.

## Screen Awareness — Step 2

When explicitly asked what is on the current screen, Veronica can capture the
primary display once and ask a locally running Ollama vision model to describe
or answer a question about it. Capture uses Pillow's `ImageGrab.grab()`. The
PIL image is encoded in memory for the local Ollama `/api/chat` request and
closed immediately after processing. No screenshot file is created; the image
is not sent to Tavily or another cloud service and is not persisted in SQLite
or conversation history. Screenshot-derived answers are returned to the user
but redacted from the session's retained chat history.

Configure `OLLAMA_VISION_MODEL` independently of `OLLAMA_MODEL`:

```powershell
$env:OLLAMA_VISION_MODEL = "a-vision-model-already-installed-locally"
```

The configured model must already be installed in local Ollama and support
image input. Veronica does not select a default vision model, fall back to the
text-only model, or pull/download a model. If the variable is unset or the
configured model is not available locally, screen understanding reports that
it is unavailable without capturing the display. The existing `OLLAMA_BASE_URL`
and `OLLAMA_TIMEOUT` settings are reused; the client enforces a loopback-only
HTTP endpoint.

Screen understanding is exposed through the existing opt-in tool-calling path
(`WEB_SEARCH_ENABLED=true`). It captures only after the model selects the tool
for an explicit screen-related request. Only the user's bounded question and
the in-memory capture go to the configured local Ollama service. Mouse and
keyboard control, clicking, typing, window manipulation, automation, OCR,
continuous monitoring, and screen recording are not part of this step.
The separate `screenshot` metadata tool remains available and does not send
its image to any model.

Registry logs include tool name, outcome, and elapsed time, but omit
parameters, results, and exception messages to avoid exposing sensitive data.
No arbitrary shell execution, browser automation, or webpage fetching is
provided. `OpenURLTool` only asks the default browser to open the validated
URL; it does not automate or inspect the browser. The existing Ollama tool
loop is bounded to four calls per turn; tool requests after the limit are not
executed.

The separate `OllamaToolCallingService` converts registered tools into
Ollama's native `tools` function definitions, handles assistant `tool_calls`,
submits registry results as `role: "tool"` messages, and requests a final
assistant response. It limits tool invocations per conversation to four by
default, then asks once more with no tool definitions; tool requests from that
final turn are rejected, not executed. When Web Search is enabled, the normal
`AIService` path delegates to this existing service; when disabled it continues
to use `OllamaClient.generate_response()` unchanged. Only the final assistant
response returns to the CLI display and optional Microsoft Edge TTS; tool
requests and results are not separately displayed or spoken.

For compatibility with `llama3.2`, the tool loop accepts only a complete,
valid `{"name":"web_search","parameters":{...}}` object when the model emits
that exact envelope as assistant content instead of using native `tool_calls`.
Malformed, embedded, or otherwise invalid tool-like text is rejected and
never returned as an assistant answer or executed. With Web Search enabled,
the current date is added dynamically from the local system clock so relative
date requests have application context; no year is hardcoded.

Persistent memory is saved only when explicitly requested. It is stored at
`data/veronica_memory.db` by default; configure `MEMORY_DATABASE_PATH` to use a
different local path. Veronica retrieves at most `MAX_RELEVANT_MEMORIES` (5 by
default) matching memories for a model request. Use `/remember <text>`,
`/memory`, `/memory-search <query>`, and `/forget <id>` to manage memories.
`/clear-memory` asks for a separate `YES` confirmation before deleting anything.
Obvious passwords, API keys, tokens, and private keys are refused. Memory is
never sent to a cloud service.

The `.env.example` file documents configuration values but is not loaded
automatically. It contains no credentials. Veronica never downloads models
automatically. Start Ollama separately with `ollama serve` if necessary.
