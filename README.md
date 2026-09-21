<p align="center">
  <b><a href="README.md">English</a></b> · <a href="README.zh-CN.md">中文</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img src="https://img.shields.io/badge/Upstream-Hermes%20Agent-blueviolet?style=for-the-badge" alt="Upstream: Hermes Agent"></a>
  <a href="https://github.com/QuantumNous/new-api"><img src="https://img.shields.io/badge/Upstream-new--api-2496ED?style=for-the-badge" alt="Upstream: new-api"></a>
</p>

# Hermes Agent ☤
<p align="center">
  <a href="https://hermes-agent.nousresearch.com/">Hermes Agent</a> | <a href="https://hermes-agent.nousresearch.com/">Hermes Desktop</a>
</p>
<p align="center">
  <a href="https://github.com/SeerBench/hermes-multiuser-web-service/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img src="https://img.shields.io/badge/Upstream-Hermes%20Agent-blueviolet?style=for-the-badge" alt="Upstream: Hermes Agent"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

This is a **fork** of upstream Hermes, not a re-implementation. The agent loop, skill system, memory provider stack, model-provider plugins, and 25+ gateway adapters all come directly from upstream — untouched. What we add is one new platform adapter (`web_chat`), the per-user isolation primitives that go with it, and the thin glue layer that talks to a new-api-compatible upstream — all packaged so `git pull upstream main` stays merge-conflict-free in perpetuity.

Use any model you want — [Nous Portal](https://portal.nousresearch.com), OpenRouter, OpenAI, your own endpoint, and [many others](https://hermes-agent.nousresearch.com/docs/integrations/providers). Switch with `hermes model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Seven terminal backends — local, Docker, SSH, Singularity, Modal, Daytona, and Vercel Sandbox. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

`new-api` is the example we test against, but any OpenAI-compatible billing gateway that speaks `GET /v1/models` for key validation and `POST /v1/chat/completions` for inference works — One API, Helicone, LiteLLM proxy, your own internal gateway, etc.

---

## Why this split?

Building yet another user-management + token-counting + Stripe-integration stack on top of every chat front-end is wasted engineering. new-api (and its ecosystem) already does all of that better than a hobby project ever will. So this fork's job narrows:

**Hermes provides** the agent loop, tools, skills, memory, and SSE-streaming chat surface.
**new-api provides** user accounts, API keys, per-key metering, billing, model routing, rate limits.
**This fork** is the bridge — a multi-user chat front-end whose users authenticate with new-api keys and whose LLM calls route through new-api.

Concretely, what the fork still does itself:

- **Per-user conversation history** (Hermes session DB filtered on `user_id`)
- **Per-user memory** (`MEMORY.md`, `USER.md`, every provider's cache — all isolated by workspace)
- **Per-user filesystem workspaces** at `$HERMES_HOME/web_workspaces/<user_id>/`
- **Sandboxed file tools** (`web_file_*`) that mirror upstream `read_file` / `write_file` / `patch` / `search_files` but reject any path that escapes the user's workspace
- **Per-user skill management** (`web_skill_*`) — every user sees a merged view of the operator's global skill library plus their own private skills (user version overlays global on name collision); install/delete only ever touch the user's own `<workspace>/skills/`
- **Zero-key web research out of the box** — `web_search` (DuckDuckGo via `ddgs`) and `web_extract` (the fork-bundled `http-fetch` provider) both work on a fresh install with no paid API key; point `web.extract_backend` at Firecrawl/Tavily/Exa/Parallel to upgrade
- A new gateway **HTTP adapter** (`gateway/platforms/web_chat.py`) on port 8643 with cookie auth and SSE streaming
- A minimal **React SPA** (`web-chat/`) — 65 KB gzipped JS, no UI framework, no router library
- **Encrypted-at-rest key storage** (Fernet under a server-side master key) so a paste of the key at first login is enough — no need to re-enter it on every browser restart

And what the fork no longer does, because it was redundant with what new-api ships:

- ❌ No email/password registration. There's no register endpoint.
- ❌ No API-key minting. Keys come from new-api's admin panel; this gateway only validates them.
- ❌ No local quota. Billing and limits live upstream.
- ❌ No `argon2-cffi` dependency. Password hashing has nothing to hash.

The user_id that anchors workspaces is **derived** from `sha256(api_key)[:12]` — deterministic, one-way, so the same key in any browser on any machine lands the user in the same conversation history. No central user table needed; new-api is the only source of identity.

---

<a id="screenshots"></a>
## Screenshots

> ⚠️ The screenshots below predate the new-api integration and still show the now-removed email-register flow and per-user quota panel. The current login is a single API-key paste modal that pops up the first time a user hits Send. Updated screenshots are on the roadmap; the streaming-chat screenshot is still representative.

<table>
  <tr>
    <td width="100%" valign="top">
      <a href="assets/screenshots/03-chat-streaming.png"><img src="assets/screenshots/03-chat-streaming.png" alt="Streaming chat with tool events" /></a>
      <p><sub><b>Streaming chat with tool events.</b> SSE token frames render incrementally; tool calls (<code>web_search</code> shown here) get an inline row with preview + duration. In the current build the header quota badge is gone — billing happens in new-api now.</sub></p>
    </td>
  </tr>
</table>

---

## Why this fork exists

Upstream Hermes Agent is a brilliant single-user CLI and single-tenant gateway. It does **not** ship a multi-user web product because that was never the upstream's goal. But the agent core — tools, skills, memory, model routing, sandboxed terminal backends — is exactly what you want for a self-hosted "ChatGPT-but-with-real-tools" service for a small team, a family, a community, or a research group. So this fork adds:

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs Hermes without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/NousResearch/hermes-agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\hermes\git` — no admin required, completely isolated from any system Git install). Hermes uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead. Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://hermes-agent.nousresearch.com/docs/getting-started/termux). On Termux, Hermes installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\hermes`; WSL2 installs under `~/.hermes` as on Linux.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
hermes              # start chatting!
```

### Troubleshooting

#### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus (Bitdefender, Windows Defender, etc.) quarantines `uv.exe` from the Hermes `bin` folder (`%LOCALAPPDATA%\hermes\bin\uv.exe`), this is a **false positive**. The file is Astral's `uv` — the Rust Python package manager Hermes bundles to manage its Python environment. ML-based antivirus engines commonly flag unsigned Rust binaries that download and install packages.

**To verify your copy is authentic:**

```powershell
# Install GitHub CLI if needed
winget install --id GitHub.cli

# Login to GitHub
gh auth login

# Run verification
$uv = "$env:LOCALAPPDATA\hermes\bin\uv.exe"
$ver = (& $uv --version).Split(' ')[1]
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = "$env:TEMP\uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip -UseBasicParsing
gh attestation verify $zip --repo astral-sh/uv
Expand-Archive $zip "$env:TEMP\uv_x" -Force
(Get-FileHash "$env:TEMP\uv_x\uv.exe").Hash -eq (Get-FileHash $uv).Hash
```

If attestation says "Verification succeeded" and the last line prints `True`, you're good.

**To whitelist Hermes:**
- **Windows Defender:** Run PowerShell as Admin → `Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\hermes\bin"`
- **Bitdefender:** Add an exception in the Bitdefender console (Protection > Antivirus > Settings > Manage Exceptions)
- Whitelist the **folder**, not the file hash — Hermes updates `uv` and the hash changes every version

For more context, see the upstream Astral reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

---

## Is this fork for you?

```bash
hermes              # Interactive CLI — start a conversation
hermes model        # Choose your LLM provider and model
hermes tools        # Configure which tools are enabled
hermes config set   # Set individual config values
hermes config get   # Print individual config values
hermes gateway      # Start the messaging gateway (Telegram, Discord, etc.)
hermes setup        # Run the full setup wizard (configures everything at once)
hermes claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
hermes update       # Update to the latest version
hermes doctor       # Diagnose any issues
```

- **Sub-package isolation.** All multi-user code lives under `gateway/web/`. Importing the package does not touch the rest of Hermes; nothing outside is rewired.
- **Mirror, don't modify.** `chat_runner.py` is a parallel implementation of `api_server.py`'s agent factory, not a refactor of it. ~150 LOC of duplication in exchange for zero merge conflicts against the most-edited file in upstream.
- **Wrap, don't fork.** Sandboxed file tools import and call `tools/file_tools.py` functions as-is and only add a `confine_path()` guard. Upstream changes to file tools land for free.
- **Toolset, not core, registration.** New tools (`web_file_*`) are added to a dedicated `hermes-web-chat` toolset in `toolsets.py` — the only edit outside the sub-package.
- **Optional dependency, opt-in extra.** `argon2-cffi` is behind the `[web-chat]` extra; nothing forces this dep on users who never run the web service.
- **No edits to load-bearing files.** `run_agent.py`, `cli.py`, `gateway/run.py`, `hermes_cli/main.py` are untouched. The `CLAUDE.md` ground rule that plugins must not modify core is honored here even though this is a fork, not a plugin.

The only changes outside `gateway/web/` are: (1) one toolset entry in `toolsets.py`, (2) a `user_id` column threaded through `SessionDB` writes (commit `2ce65f980`), (3) `web_chat` registered in the gateway platform enum. Each is a small, well-contained patch designed to be re-applied by hand or via `git rerere` if upstream rewrites the file.

In practice, `git fetch upstream && git rebase upstream/main` is the maintenance loop.

---

## When to use this fork

Hermes works with whatever provider you want — that's not changing. But if you'd rather not collect five separate API keys for the model, web search, image generation, TTS, and a cloud browser, **[Nous Portal](https://portal.nousresearch.com)** covers all of them under one subscription:

- **300+ models** — pick any of them with `/model <name>`
- **Tool Gateway** — web search (Firecrawl), image generation (FAL), text-to-speech (OpenAI), cloud browser (Browser Use), all routed through your sub. No extra accounts.

One command from a fresh install:

```bash
hermes setup --portal
```

That logs you in via OAuth, sets Nous as your provider, and turns on the Tool Gateway. Check what's wired up any time with `hermes portal info`. Full details on the [Tool Gateway docs page](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-gateway).

You can still bring your own keys per-tool whenever you want — the gateway is per-backend, not all-or-nothing.

---

## Hardware sizing

Numbers assume the upstream LLM is **cloud-hosted** (routed through new-api → OpenAI / Anthropic / Nous Portal / OpenRouter / your own provider). The bottleneck shifts depending on box size:

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `hermes`                                      | Run `hermes gateway setup` + `hermes gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

Disk: ~2 GB for the venv + code, then per-user data grows with use.

**Active** = "in the middle of an agent loop right now". A user reading the assistant's reply or typing the next message is *online* but not active. Typical chat usage has a 1:5 to 1:10 active-to-online ratio.

Practical observations:

- **Concurrent agents are no longer bounded by one shared upstream key**. Each user has their own new-api key with its own quota, so the ceiling is whatever new-api or the underlying provider permits per-key, multiplied by N users.
- **Context compression** in the agent loop is a momentary CPU spike that briefly doubles RSS. Multiple users compressing simultaneously can OOM a 4 GB box if you don't cap concurrency. `WEB_CHAT_MAX_CONCURRENT_AGENTS` (default 12) is the safety valve.
- **SQLite is fine until ~5 RPS sustained**. WAL + jitter retry handles bursts. Above that, migrate to Postgres.

---

## Documentation

All documentation lives at **[hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://hermes-agent.nousresearch.com/docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://hermes-agent.nousresearch.com/docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://hermes-agent.nousresearch.com/docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://hermes-agent.nousresearch.com/docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, Hermes can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`hermes setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
hermes claw migrate              # Interactive migration (full preset)
hermes claw migrate --dry-run    # Preview what would be migrated
hermes claw migrate --preset user-data   # Migrate without secrets
hermes claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.hermes/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `hermes claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://hermes-agent.nousresearch.com/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors — use the standard installer, then work from the
full git checkout it creates at `$HERMES_HOME/hermes-agent` (usually
`~/.hermes/hermes-agent`). This matches the layout used by `hermes update`, the
managed venv, lazy dependencies, gateway, and docs tooling.

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
cd "${HERMES_HOME:-$HOME/.hermes}/hermes-agent"
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

Manual clone fallback (for throwaway clones/CI where you intentionally do not
want the managed install layout):

Create the venv outside the cloned source tree — a venv inside the directory
the agent operates from can be wiped by a relative-path command the agent runs
against its own checkout, destroying the running runtime mid-session.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv ~/.hermes/venvs/hermes-dev --python 3.11
source ~/.hermes/venvs/hermes-dev/bin/activate
uv pip install -e ".[all,dev]"
scripts/run_tests.sh
```

> **Windows note:** the upstream single-user agent installs natively on Windows via `powershell -ExecutionPolicy Bypass -File scripts/install.ps1`. The multi-user web service itself targets Linux/macOS servers — on Windows, run it under WSL2.

Open `http://127.0.0.1:8643/` in a browser. The chat UI is already visible — type a message and hit Send. A modal will pop up asking for the API key. Paste the one the admin gave you. The cookie that comes back is good for 7 days; subsequent visits go straight to chat.

For production deployment: front the gateway with TLS (Caddy / nginx / Traefik), set `cookie_secure: true`, only then change `host: 0.0.0.0` — the adapter **refuses to start** if you skip TLS on a non-loopback bind. Full checklist in [`docs/user-guide/web-chat.md`](docs/user-guide/web-chat.md).

**Updating a deployed box:** a plain `git pull` won't refresh the UI — the SPA bundle (`gateway/web/_static/`) is `.gitignore`'d and must be rebuilt. Run `./update-web.sh` to automate pull → rebuild SPA → restart → health-check (use `--systemd <unit>` if the gateway is systemd-managed). Schema changes apply automatically on startup (`CREATE TABLE IF NOT EXISTS`), so there's no migration step. See [Updating a deployment](docs/user-guide/web-chat.md#updating-a-deployment).

---

## HTTP surface

The single auth mode is the `hermes_session` cookie, issued by `/api/auth/login`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/api/auth/login` | none | validate new-api key against upstream + set cookie |
| `POST` | `/api/auth/logout` | cookie | expire cookie + delete server-side row |
| `GET`  | `/api/me` | yes | current `user_id` + first/last-seen timestamps |
| `GET`  | `/api/conversations` | yes | list user's sessions, filtered by `user_id` |
| `GET`  | `/api/conversations/{id}` | yes | load one session's transcript (own sessions only) |
| `GET`  | `/api/commands` | yes | list slash commands available to the user |
| `POST` | `/api/command` | yes | run a slash command |
| `POST` | `/api/chat` | yes | **SSE stream** of agent response |
| `GET`  | `/api/healthz` | none | liveness probe |
| `GET`  | `/static/*`, `/assets/*` | none | SPA assets |
| `GET`  | `/` | none | SPA shell |

No `/api/auth/register`, no `/api/keys/*`, no `/api/usage` — those belong to new-api.

### `POST /api/auth/login` validation flow

```
{ "api_key": "sk-..." }
        │
        ▼
GET {NEW_API_BASE_URL}/v1/models     Authorization: Bearer sk-...
        │
        ├─ 2xx                 → derive user_id = "u_" + sha256(key)[:12]
        │                        upsert user row, encrypt key (Fernet), set cookie
        ├─ 401 / 403           → return 401  code=invalid_key
        ├─ other 4xx           → return 502  code=misconfigured
        └─ 5xx / 429 / network → return 503  code=upstream_unreachable
```

### SSE event protocol (`POST /api/chat`)

| event | payload | when |
|---|---|---|
| `token` | `{"text": "..."}` | streaming assistant token |
| `tool_start` | `{"tool": "...", "preview": "..."}` | tool call begins |
| `tool_end` | `{"tool": "...", "duration": 1.2, "error": false}` | tool call returns |
| `reasoning` | `{"text": "..."}` | model reasoning (provider-dependent) |
| `done` | `{"session_id": "...", "usage": {...}}` | terminal frame |
| `error` | `{"message": "...", "code": "..."}` | fatal mid-stream error |

On 401 mid-session (cookie expired or master key rotated) the SPA opens the key prompt again and resends the original message after re-auth.

---

## Multi-browser behavior

Because `user_id = sha256(api_key)[:12]` is deterministic, the same key in any browser maps to the same workspace and conversation history.

| Scenario | Behavior |
|---|---|
| B browser logs in with the same key A used | B's conversation list shows everything A created |
| B reopens a session A started | Full history visible |
| A creates a new session while B has the list open | B needs to refresh to see it (no live push) |
| A and B both open the same session and A sends a message | A streams; B sees the new turn after refresh |
| A and B send to the same session concurrently | SQLite write lock serialises; UI doesn't auto-sync |

Real-time cross-browser push is not implemented in v0.15. Refresh-level sync only.

---

## Security model

**What's isolated by design:**

- **Conversations** — `sessions.user_id` filter on every `list_sessions_rich` / `search_messages` call.
- **Memory** — `enter_user_context` rebinds `HERMES_HOME` via ContextVar; `MemoryManager` and every provider read `get_hermes_home()` and write under `web_workspaces/<user_id>/memories/`. Zero-touch — no agent-internal code modified.
- **Filesystem (tools)** — `web_file_*` route every path through `confine_path` which rejects anything outside the user's workspace. V4A multi-file patches are **refused outright** because their inner file paths can't be inspected without parsing the V4A format.
- **Upstream API key** — encrypted with Fernet under `$HERMES_HOME/web_users_master.key` (chmod 600, auto-generated on first start). Decrypted in memory per request, never logged. Injected into the AIAgent's LLM client via a per-task ContextVar so concurrent requests can't see each other's key.
- **Cookie sessions** — `HttpOnly` + `SameSite=Lax` + optional `Secure`; server-side row in `web_sessions` enables instant revocation (logout invalidates the row, not just the cookie).

**What's NOT isolated** (deliberate scope decisions):

- **OS-level shell.** The default toolset excludes `terminal`, `process`, `code_execution`, `browser_*`, `computer_use`. Don't add them back without an OS-level sandbox (Docker / firejail / chroot). The Python-layer `confine_path` defends against accidental path traversal, not kernel exploits.
- **Kernel exploits.** `confine_path` is a Python-layer guard, not a defense against a compromised CPython or a kernel CVE.
- **Upstream $-cost overruns.** Billing happens at the new-api layer. If you need hard caps, set per-key quotas in new-api's admin panel — this gateway does not duplicate that.

If `~/.hermes/web_users_master.key` is ever compromised, delete it; a fresh key auto-generates on next start. Every existing cookie session is invalidated (their encrypted key payloads no longer decrypt), and users get re-prompted for their new-api key — no data loss, since `user_id` is derivable from the key itself.

---

## Testing & quality

This fork ships with automated tests for every fork-specific module. All passing on `main`:

| Layer | File |
|---|---|
| User-id isolation in SessionDB | `tests/hermes_state/test_user_id_filtering.py` |
| UserStore (user records, web sessions) | `tests/gateway/test_web_users.py` |
| Sandbox + workspace contextvars | `tests/gateway/test_web_sandbox.py` |
| Cookie auth middleware | `tests/gateway/test_web_auth_middleware.py` |
| Chat runner (AIAgent factory + ContextVar key injection) | `tests/gateway/test_web_chat_runner.py` |
| HTTP adapter (login flow, /me, /conversations, chat auth gate) | `tests/gateway/test_web_chat_adapter.py` |
| Sandboxed `web_file_*` tools | `tests/gateway/test_web_sandboxed_file_tools.py` |
| Upstream key validator (new-api `/v1/models` probe) | `tests/gateway/test_web_upstream_validator.py` |
| Upstream key ContextVar + user_id derivation | `tests/gateway/test_web_upstream_key.py` |
| Fernet KeyVault (encrypt / decrypt / master key file) | `tests/gateway/test_web_key_storage.py` |
| Transcript load (`GET /api/conversations/{id}`) | `tests/gateway/test_web_get_conversation.py` |
| Per-user sandboxed skill tools (`web_skill_*`) | `tests/gateway/test_web_sandboxed_skills.py` |
| Slash-command surface (`/api/commands`, `/api/command`) | `tests/gateway/test_web_commands.py` |
| Auxiliary BYO model router | `tests/gateway/test_web_aux_byo_router.py` |
| Zero-key `http-fetch` web_extract provider | `tests/tools/test_web_providers_http_fetch.py` |

Run with the project test wrapper (CI-parity hermetic env):

```bash
scripts/run_tests.sh tests/gateway/test_web_*.py tests/hermes_state/test_user_id_filtering.py
```

The most load-bearing tests prove the multi-user isolation contract — that ContextVars are asyncio-task-local (not threadlocal), so one user's request can't leak into another's workspace or billing account under concurrent load:

- **`test_run_propagates_upstream_key_contextvar_to_worker_thread`** (`test_web_chat_runner.py`) — the regression for the "no-key-required" 401 incident: the runner executes the AIAgent in a `loop.run_in_executor` worker thread, and this test proves the per-request upstream key ContextVar actually reaches that thread (via `copy_context().run`) instead of falling back to the global placeholder.
- **`test_contextvar_propagates_to_asyncio_task`** (`test_web_upstream_key.py`) — confirms the upstream-key ContextVar is task-local, so concurrent chat tasks each see their own key.
- **`test_derive_user_id_is_deterministic_across_calls`** / **`test_derive_user_id_differs_for_different_keys`** (`test_web_upstream_key.py`) — the `user_id = sha256(key)[:12]` anchor is stable per key and distinct across keys, the property every workspace/session/billing boundary hangs off.

---

## Repository layout

```
.
├── gateway/
│   ├── platforms/web_chat.py        HTTP adapter — cookie auth + routes + SSE
│   └── web/                         ← all multi-tenant code lives here
│       ├── users.py                 UserStore (user records + cookie sessions)
│       ├── auth.py                  cookie middleware + KeyVault wiring
│       ├── sandbox.py               enter_user_context / confine_path
│       ├── upstream_key.py          per-request upstream-key ContextVar + user_id derivation
│       ├── upstream_validator.py    pre-login key probe against new-api /v1/models
│       ├── key_storage.py           KeyVault (Fernet + on-disk master key)
│       ├── chat_runner.py           AIAgent factory (mirror of api_server)
│       ├── aux_byo_router.py        per-user bring-your-own auxiliary model routing
│       ├── web_commands.py          slash-command surface (/api/commands, /api/command)
│       └── tools/
│           ├── __init__.py          (side-effect register on import)
│           ├── sandboxed_file_operations.py     web_file_* tools
│           └── sandboxed_skill_manage.py        web_skill_* tools (per-user + global)
│
├── plugins/web/http_fetch/          ← fork-bundled zero-key web_extract provider
│   ├── plugin.yaml                  kind: backend, provides http-fetch
│   └── provider.py                  httpx GET + stdlib HTML→text
│
├── web-chat/                        ← React SPA → builds to gateway/web/_static/
│   ├── src/
│   │   ├── App.tsx                  hash router + nav, no auth gate
│   │   ├── api.ts                   typed fetch wrappers + SSE async generator
│   │   ├── main.tsx                 React entrypoint
│   │   ├── styles.css               single global stylesheet (dark + light)
│   │   ├── pages/{Chat,Settings}Page.tsx
│   │   └── components/{KeyPromptModal,ConversationList,ToolEvent}.tsx
│   ├── package.json                 react 19 + vite 7 + ts 5
│   └── vite.config.ts               proxies /api → :8643 in dev
│
├── tests/
│   ├── hermes_state/test_user_id_filtering.py
│   ├── gateway/test_web_*.py        13 files covering the gateway fork surface
│   └── tools/test_web_providers_http_fetch.py   zero-key extract provider
│
├── docs/user-guide/web-chat.md      operator guide (new-api integration walk-through)
│
└── (everything else from upstream Hermes Agent, untouched)
```

---

## Roadmap

Shipped since the first cut:

- [x] **GET /api/conversations/{id}** — transcript history loads when switching sessions (`test_web_get_conversation.py`)
- [x] **Per-user skill management** — `web_skill_*` tools with a merged global + private library (`test_web_sandboxed_skills.py`)
- [x] **Zero-key web research** — `web_search` (ddgs) + `web_extract` (bundled `http-fetch`) work with no paid key (`test_web_providers_http_fetch.py`)

In rough order of useful next steps:

- [ ] **Refreshed screenshots** matching the new-api login flow
- [ ] **Plugin-hook proposal to upstream** — `register_gateway_platform()` on `PluginManager` so this whole fork can be re-published as a standalone plugin and the surgical patches dissolve
- [ ] **Optional Postgres backend** for `web_users.db` when single-box SQLite tops out
- [ ] **OAuth / SSO** at the proxy layer for company deployments (cookie still gates the chat surface)
- [ ] **OS-level per-user sandbox** wired through upstream's existing Docker terminal backend
- [ ] **Push-based multi-browser sync** (per-user SSE event-bus) for users who keep the app open on multiple devices

The user-id propagation fixes are intended to be offered back upstream as a PR — real bugs in the shared `user_id`-column infrastructure, with no behavioral change for existing single-user callers.

---

## Acknowledgements & license

- **Upstream agent**: [Nous Research / hermes-agent](https://github.com/NousResearch/hermes-agent) — the entire agent loop, skill system, memory stack, tool registry, 25+ gateway platforms, model-provider plugins, and CLI come from there. The fork is a thin operational layer on top of that work.
- **Upstream billing gateway**: [new-api](https://github.com/QuantumNous/new-api) — example reference, but any OpenAI-compatible upstream that responds to `GET /v1/models` works (One API, Helicone, LiteLLM proxy, internal gateways, etc.).
- **License**: MIT, matching upstream — see [`LICENSE`](LICENSE).

Further reading:

- [`docs/user-guide/web-chat.md`](docs/user-guide/web-chat.md) — operator-focused guide (setup, HTTP surface, capacity, production checklist, admin tasks).
- [`web-chat/README.md`](web-chat/README.md) — SPA development notes.
- For upstream agent behavior (skills, memory, tools, model routing), see [hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs/) — everything there applies here too, unmodified.
- [`AGENTS.md`](AGENTS.md) (~1100 lines) is the upstream engineering guide — canonical for anything below the multi-user layer.
- [`CLAUDE.md`](CLAUDE.md) is the orientation file for working in this repo with [Claude Code](https://claude.com/claude-code).
