# Changelog

## v0.8.0

192 commits

### New Features (7)

- **Evomem Knowledge Graph Memory** — a comprehensive long-term memory engine with primary and fallback storage backends, knowledge-graph integration, and semantic recall. Agents now remember facts across conversations and can traverse relationships between entities, making them genuinely stateful over time.
- **KB System v2** — three new tools deepen the knowledge base experience: a graph traversal tool lets agents follow wiki-link connections between KB documents, enhanced listing surfaces staleness and graph-awareness metadata, and a canonical `_kb_index.md` index keeps the knowledge graph navigable. Agents also receive coaching prompts to maintain KB graph links automatically.
- **Sub-Agent System** — the `/sub` slash command lets you spawn sub-agents directly from chat for parallel work. Sub-agents execute without planning delays, deliver responses through inter-agent forwarding, and are protected by naming-pattern enforcement. New `inter_agent_clear_context` and `builtin_tools_enabled` settings give fine-grained control over agent behavior.
- **/detach Slash Command** — move long-running background processes (builds, downloads, compilations) out of the agent loop so you can keep chatting while work continues. Progress is tracked persistently and the agent notifies you when the job completes.
- **/investigate Slash Command** — inspect any agent's context from chat with `/investigate <agent-id> <context>`, surfacing session state, tool configuration, and runtime diagnostics without leaving the conversation.
- **Syntax Highlighting & Rich Terminal in Chat** — code blocks now render with syntax highlighting via highlight.js. Bash execution output appears in a dark terminal-styled block. Copy buttons appear on code blocks and blockquotes. A live artifacts strip appears between thinking and final response.
- **Kanban Task Workflow** — tasks now carry a `created_by` owner column with owner-based delete permission. `task_id` is returned at the top level of creation responses. Agents auto-post their final answer as a kanban comment when a task completes.

### Plugin's Features (3)

- **Token Monitor** — per-agent and per-model-source token usage tracking with a cost dashboard, giving visibility into LLM spending across all agents (token-monitor plugin).
- **Evonet Multi-Server Manager** — a dropdown UI and server manager GUI for the Evonet connector, letting you switch between multiple remote devices without reconfiguration (evonet plugin).
- **Evonet Exactly-Once Execution** — tool execution across WebSocket reconnects is now idempotent, preventing duplicate command runs when the tunnel re-establishes (evonet plugin).

### Enhancements (32)

- **Flat Repository Architecture** — the legacy supervisor daemon, release-mode detection, and multi-directory app-root resolution have been removed. The codebase now follows a flat single-repo structure, simplifying deployment paths and eliminating an entire class of path-resolution bugs.
- **Security Hardening Suite** — API rate limiting protects all endpoints with tiered limits and atomic enforcement. Security audit logging records authentication and authorization events for forensic traceability. User blocking prevents abusive accounts from accessing the platform. Login rate-limiter state persists across restarts via SQLite.
- **PromptPurify ML Always-On** — the L5e injection guard classifier now runs unconditionally, catching prompt injection patterns that regex-based guards miss, with a false-positive fix for benign security terminology.
- **PEM Private Key Detection** — the platform detects when private keys appear in tool output or file operations and routes through a user approval flow, preventing accidental key exposure to LLM providers.
- **Workspace Boundary Enforcement** — the Read, Grep, and Glob tools now enforce workspace directory boundaries, preventing agents from reading files outside their sandbox.
- **Session Archive** — `/clear` data is now archived to a dedicated `session_archive.db` instead of being permanently deleted. Recover cleared conversations when needed.
- **agent_info Tool** — agents can inspect any other agent's full configuration (tools, skills, channels, KB, artifacts, models) from within a conversation, enabling self-diagnostic workflows.
- **fetch_artifact Tool** — the reverse of `save_artifact`: agents can fetch files from the host artifacts directory back into the sandbox for inspection or processing.
- **Collapsible Inter-Agent Messages** — `[AGENT/...]` messages in chat now collapse into a compact header, reducing visual noise in multi-agent conversations.
- **System Prompt Full-Screen Editor** — a modal editor with dirty-check confirmation, ESC-to-close, and Ctrl+S save support for editing agent system prompts without cramped textareas.
- **Injected System Variables** — `{{key}}` placeholders in system prompts are expanded from message metadata, enabling dynamic prompt injection per conversation turn.
- **CRUD Rate Limit Raised** — the CRUD endpoint rate limit increased from 30 to 120 requests per minute, reducing friction during bulk operations.
- **Blocked User Admin UI** — an admin interface for viewing and managing blocked users, integrating with the user-blocking enforcement system.
- **Public History Warning** — a warning dialog informs users before they enable public session history, preventing accidental exposure of private conversations.
- **Performance: Chat Messages Index** — a composite database index on `(session_id, created_at DESC)` accelerates message pagination queries.
- **Doctor Improvements** — five new diagnostic sections: evomem safety check, promptpurify model check, list_artifacts consistency, asset build check, and LLM provider check (now optional). Doctor also suggests `--fix` commands after running.
- **Tailwind CSS v4 Build Pipeline** — a `build_tailwind.sh` script builds the UI stylesheets from the Tailwind v4 source, replacing ad-hoc CSS management.
- **Process Tracker Hardening** — enhanced process group and container cleanup for both local and Docker backends, reducing orphaned process leaks.
- **Avatar Compression** — avatars are now stored with compression variants, reducing bandwidth and improving load times on slow connections.
- **Active Session Indicator** — a green gradient on the sidebar highlights which agent session is currently active, so you always know where the conversation is happening.
- **Kanban Skeleton Loading** — the Kanban board shows animated skeleton placeholders while tasks load, giving immediate visual feedback instead of a blank screen.
- **Lightbox Filename Overlay** — image filenames appear in the lightbox overlay for quick identification when browsing multiple images.
- **Knowledge Tab Searchbar** — a search bar on the agent detail Knowledge tab lets you filter KB documents by name without scrolling through the full list.
- **/cd and /cwd for Remote Workplaces** — the directory navigation slash commands now work with agents on remote or tunnel-connected workplaces.
- **Attachment Info Injection** — file path metadata is injected into agent context when files are uploaded via the web chat UI.
- **Resume Evaluation** — the evaluation system now accepts domain-level input for more accurate session resumption.
- **Image Serving Concurrency** — images and avatars are served concurrently with caching, improving page load performance.
- **Sub-Agent Direct Execution** — sub-agents skip the planning phase and execute directly, reducing turn latency for delegated tasks.
- **Summarizer Filters** — `bash_exec` and `slash_command` messages are filtered from recap and summary context, keeping recaps focused on conversation content.
- **Fallback Model Reset** — the active fallback model flag resets on inter-agent clear, preventing stale model assignments.
- **Built-In Tools Toggle** — each agent can now independently enable or disable built-in tools via an advanced setting, rather than a global flag.
- **Bash Command Param** — the bash tool now supports a `command` parameter for direct command execution alongside the existing `script` parameter.

### Bug Fixes (43)

- **More Robust Image Attachment Handler** — the image feed is decoupled from the LLM pipeline. A dedicated `describe_image` tool gives agents control over when and how images are processed, fixing inconsistent image handling across different models and providers.
- **SSE Connection Storm** — stale connection counts now reset on startup, and the connection cap was raised, stopping the `too_many_sse_connections` error storm that flooded logs.
- **SSE Exponential Reconnect** — the SSE client uses exponential backoff for reconnects, preventing connection-limit exhaustion during network interruptions.
- **SSE Chat Sequence Gaps** — a contiguous `_chat_seq` counter in the unified chat producer eliminates phantom gap-fill requests that caused duplicate message rendering.
- **Intermediate Response Chunks** — `response_chunk` events no longer prematurely end the live turn, fixing truncated agent responses mid-generation.
- **Sidebar Layout** — the sidebar now uses absolute positioning anchored to the app shell, filling the full viewport height without empty space, and works correctly on mobile.
- **System Balloon Chevron** — the system message balloon chevron stays right-aligned when the balloon is expanded.
- **Download Button Position** — the chat image download button moved from top-right to top-left, no longer overlapping with image content.
- **Phantom Turn Resumption** — the `system` message type is now included in unreplied-type checks, preventing phantom turn resumption after system events.
- **Injection Guard False Positive** — a P0 false positive on benign security terminology (e.g., "bypass" in normal context) has been eliminated.
- **Qwen Parser Validation** — extracted tool-call identifiers from Qwen models are now validated, preventing corrupted parameter injection.
- **Gemma4 Parser Fallback** — the LLM loop checks for Gemma4 parser availability before falling back to Qwen, fixing parse failures on Gemma models.
- **Orphaned Tool Calls** — the tool-call repair logic now properly restores orphaned calls, preventing HTTP 400 "insufficient tool messages" errors.
- **Loop Detection Forwarding** — force-stop termination from loop detection now properly forwards to the delegating agent.
- **Calculator Routing** — the calculator tool routes to the real math backend instead of a broken Python mock.
- **CRUD Rate Limit Race** — `check_rate_limit` is now atomic, eliminating UNIQUE constraint violations under concurrent requests.
- **Chat Reads Exclusion** — cheap chat read/poll requests are excluded from the 10/min chat rate-limit tier, preventing rate-limiting of normal browsing.
- **CSRF Cookie SameSite** — the CSRF cookie `SameSite` attribute changed from `Strict` to `Lax`, fixing cross-origin navigation issues while maintaining protection.
- **CRLF Sanitization** — carriage-return characters in URL parameters are sanitized, preventing HTTP header injection.
- **Health Endpoint Redaction** — Docker version and disk usage details are redacted from `/api/health`, closing an information disclosure vector.
- **Approval Flow** — `approval_resolved` events now emit before re-executing approved tools, preventing race conditions in the approval workflow.
- **Kanban Avatars** — agent avatars now display correctly on the Kanban board, with initial-based fallbacks for agents without custom avatars.
- **Kanban Sub-Agent Tasks** — parents can update sub-agent tasks, sub-agents can update parent-assigned tasks, and unassigned task status updates are properly guarded.
- **Sub-Agent Session Index** — the session index now records the sub-agent's own ID instead of the parent's, fixing session lookup for sub-agent conversations.
- **Sub-Agent Artifacts** — artifact tools and routes for sub-agents correctly use the parent agent's ID, ensuring artifacts are accessible.
- **/sub Command Visibility** — super agents can now see and use the `/sub` command, and it's listed in `/help`.
- **Evonet Ping/Pong** — ping and pong control frames are no longer dispatched as RPC requests, preventing spurious errors in evonet logs.
- **Evonet Shell Environment** — `exec_bash` and `exec_python` on remote devices now honor the user's shell environment variables.
- **Doctor evobrain→evomem Rename** — the doctor command check uses the correct `evomem` binary name after the codebase-wide rename.
- **Doctor list_artifacts Check** — a new doctor section detects when the `list_artifacts` tool is missing from agents that have `save_artifact`.
- **Scheduler Timezone** — deterministic timezone handling prevents UTC-conversion errors that caused schedules to fire at wrong times.
- **Double Slash Command Response** — race conditions between SSE and POST delivery no longer produce duplicate slash command responses.
- **System Prompt Modal** — the system prompt editor modal now closes after a successful save.
- **Lightbox Single Image** — prev/next navigation buttons are properly hidden when the lightbox contains only one image.
- **Lightbox Navigation** — prev/next now works correctly across image artifacts, not just chat-embedded images.
- **Mobile Image Overflow** — `max-width:100%` on chat image skeletons prevents horizontal overflow on mobile screens.
- **CTRL+G Quick Search** — agent search is now case-insensitive, searches by both ID and name, and the modal position is lowered for better reachability.
- **Sidebar Height Fixes** — multiple iterations corrected the sidebar height from `100vh` through `calc(100vh - 100px)` to the final `calc(100vh - 56px)` with absolute positioning.
- **File Upload Context** — file paths are now injected into agent context when files are uploaded via the web chat UI.
- **Skills Tab Toasts** — persistent "Saved!" labels in the Skills tab are replaced with proper toast notifications.
- **Tool ID Encoding** — the `toolId` parameter is now properly encoded in the `editTool` API call, and alerts are replaced with toast notifications.
- **Evomem Recall Fields** — recall field normalization and capture title sanitization prevent YAML frontmatter parse errors in memory entries.
- **Secret Key Detection Tests** — pre-existing test failures in the secret key leak detection suite have been fixed, and tests are converted to proper pytest format.

## v0.7.0

158 commits

### New Features (10)

- **Image Lightbox** — full-featured image viewer with prev/next navigation, thumbnail sizing, and download button for chat images and artifacts. Browse visual content inline without opening new tabs or losing context.
- **Anthropic API Format Translation** — the LLM client now translates between OpenAI and Anthropic API formats, configurable per-model via an API format dropdown in the model modal. Connect Claude and other Anthropic-compatible models natively without a proxy.
- **Per-Agent Run-As-User Isolation** — configure a Linux user per agent for bash and runpy execution, with environment variables preserved across sudo boundaries. Each agent runs sandboxed under its own OS account.
- **Ctrl+G Agent Quick Search** — keyboard-driven overlay for instant agent search and navigation. Type a partial name and jump directly to any agent without touching the mouse or leaving the current page.
- **Scheduler Auto-Extend Trigger** — new trigger type that automatically extends running schedules, enabling perpetual scheduling patterns without manual renewal.
- **List Artifacts Tool** — new tool lets agents browse their artifact directory. Automatically granted to any agent that has the save_artifact tool.
- **Agent Sidebar Unread Indicators** — a blue dot and selection ring on sidebar avatars show which agents have pending responses, so you never miss a completed task while browsing elsewhere.
- **/shutdown Slash Command** — super agents can cleanly shut down the entire Evonic server from within a conversation, no terminal access needed.
- **Workplace CLI Subcommand** — manage workplaces from the command line with `evonic workplace`: list, inspect, and configure workplaces without the web UI.
- **Scheduler Log Tab** — the scheduler detail view now includes activity execution details, captured output, and timing for each scheduled run, making it possible to troubleshoot failures directly from the UI.

### Plugin's Features (2)

- **Exa-Search** — AI-powered web search capability for agents, enabling real-time information retrieval from the internet with structured JSON output and semantic content extraction (exa-search skill).
- **Obscura** — lightweight headless browser for web scraping, JS rendering, CDP server (Puppeteer/Playwright), and MCP server. A lighter alternative to PinchTab with no dependencies and a single binary (obscura skill).

### Enhancements (34)

- **Realtime SSE Consolidation** — five separate realtime event streams merged into one unified SSE endpoint, reducing browser connection overhead and eliminating race conditions between event sources.
- **PROMPTPurify L5e Injection Guard** — a compact ML classifier runs as a second-pass injection guard, catching prompt injection patterns that regex-based guards miss. Semantic analysis adds a layer beyond simple pattern matching.
- **CSRF Protection** — double-submit cookie pattern protects all state-changing endpoints against cross-site request forgery attacks. Automatically disabled during test runs.
- **Auto-Assign Non-Lazy Skill Tools** — when a non-lazy skill is assigned to an agent, its tools are now automatically registered without manual assignment. Prevents silently broken skills caused by forgotten tool configuration.
- **Evonic Doctor Consistency Checks** — two new diagnostic checks detect orphaned tool assignments: artifact tool consistency (section 9) and non-lazy skill tool consistency (section 10). Both support `--fix` to auto-correct mismatches.
- **Stale Session Injection Detection** — the runtime detects when an agent's session has been idle long enough for the context to be stale, injecting a staleness-aware prefix to keep the agent grounded. Configurable per-agent with sensitivity settings.
- **Save Artifact Source Path Routing** — artifacts can now be saved directly from file paths through sandbox and tunnel backends, eliminating the base64 encoding bottleneck for large files.
- **Evonet.md Default KB** — new super agent setups now ship with evonet.md as a default knowledge base, providing instant context about the Evonet tunnel architecture.
- **In-Place Agent Switching** — navigating between agents now swaps content without a full page reload, with soft-switch support for the super agent. Dramatically reduces wait time when bouncing between agents.
- **Unified Chat State/Summary** — `/chat/state` and `/chat/summary` merged into a single API call, halving network overhead on every chat turn.
- **Configurable Sidebar Agent Limit** — maximum visible agents in the sidebar is now configurable from System Settings instead of hardcoded.
- **Server-Side Search/Filter** — agent search and filtering moved to the backend, fixing the bug where search only matched the currently visible page.
- **Avatar Initials** — agents now display colored name-initial circles instead of generic placeholder icons, making agent identity instantly recognizable across the platform.
- **Chat Image Download Button** — every image in chat messages now has a download button overlay for one-click saving without right-click menus.
- **Build Operations Rule Injection** — agents with bash or runpy tools automatically receive instructions to run compilations inside tmux or screen sessions, preventing the agent loop from blocking during builds.
- **Artifacts Pagination** — the artifacts tab now paginates large collections with server-side search and filtering, keeping the UI responsive even with hundreds of files.
- **KB File Modal Auto-Grow** — the KB file editor textarea now auto-grows to fit content, eliminating nested scrollbars.
- **CSS Concatenation Build Script** — unified CSS build step produces a single minified stylesheet from modular source files.
- **cat_file_bytes Streaming Transfer** — file transfers across all backends use streaming instead of docker cp/shutil.copy2, supporting larger files without temporary disk copies.
- **Smart Quote Normalization** — curly/smart double quotes normalized before markdown parsing, preventing broken formatting from copy-pasted or small-model-generated text.
- **Scheduler Full Output Capture** — session_prompt output now fully captured and visible in the scheduler detail view for troubleshooting.
- **Summarization Diagnostic Logs** — skip reasons logged when summarization is bypassed, making summarization behavior debuggable.
- **Stale Boundary Event Stripping** — stale boundary events stripped from `/chat/events` to prevent ghost thinking bubbles after `/clear`.
- **Memory NULL-Dimension Backfill** — existing memories without dimension vectors backfilled so conflict detection catches all duplicates.
- **Relative Avatar Path Storage** — avatar_path stored as relative for backup/restore portability across different server deployments.
- **Telegram Auto-Populate Display Name** — agent display name automatically populated from Telegram profile data on first connection.
- **sudo -E Environment Preservation** — environment variables survive sudo elevation when running commands with run_as_user.
- **Toast on Agent Enable/Disable** — enabling or disabling agents from the detail page now shows a toast confirmation instead of silent action.
- **Python -c Instead of Heredoc** — bash execution uses `python -c` to keep stdin available for interactive `input()` calls.
- **Download Button Repositioned** — chat image download button moved to top-right overlay, keeping it accessible without cluttering the image area.
- **Allow Soft-Switch to/from Super Agent** — sessions no longer reject mode/agent change when switching to or from the super agent.
- **Workplace Detail Tab Alignment** — workplace detail page tabs now match agent_detail styling for visual consistency across the platform.
- **Slow-Request Logging** — requests exceeding 500ms logged with full path and timing for bottleneck identification.
- **Verbose Logging by Default in CLI** — CLI mode now matches GUI log output verbosity, giving consistent debugging output regardless of how you launch.

### Performance (11)

- **Agent Detail Page Speedup** — eliminated database write contention and redundant queries on agent detail page loads, cutting load time significantly.
- **SQLite Performance Tuning** — WAL mode, synchronous, and cache size PRAGMAs tuned for the platform's read-heavy workload. Thread-local connection pooling reduces WAL checkpoint pressure.
- **Buffer Events.Log Writes** — event log writes buffered to reduce filesystem directory churn on high-traffic deployments.
- **Cache app_settings** — SettingsMixin caches app_settings to avoid hitting the database on every page load.
- **Strip Empty Tool Descriptions** — OpenAI tool definitions omit empty description strings, reducing token overhead on every request.
- **DB Connection Lifecycle** — connections closed after requests with anchor to prevent WAL checkpoint stalls and file descriptor exhaustion.
- **Compiled Regex + Tool JSON Cache** — regex patterns compiled at module level and tool JSON definitions cached with mtime invalidation, eliminating repeated serialization.
- **Lazy Image Loading with Skeleton Shimmer** — chat images load on-demand with skeleton shimmer animation placeholders, improving initial page render time on image-heavy conversations.
- **O(log N) Event Boundary Lookup** — bisect-based boundary search in `get_events_in_range` for faster event retrieval.
- **LLM Client Settings Cache** — context_length, prompt_buffer, and max_retries cached with 30s TTL to avoid redundant settings reads.
- **Skill Manifest & Tool-Def Parsing Cache** — skill manifest JSON and tool-def parsing cached to avoid repeated filesystem reads on every tool invocation. Fixed a mutable cache bug where shared tool-def dicts were accidentally mutated across agents.

### Bug Fixes (36)

- **Sidebar prevents empty chat space** — max-height and align-self: flex-start on the sidebar container stops it from pushing empty space into the chat room on tall viewports.
- **PID start conflict** — single-instance prevention uses flock for atomic PID file access, fixing race conditions between parallel starts. Automatically skipped under pytest.
- **10 CI test failures resolved** — MagicMock leak across tests, API delete endpoint handling, PID file cleanup, and `_tlocal->_tls` typo in test fixtures all fixed.
- **Default KB not copied on web agent creation** — new agents created via the web UI now properly receive default knowledge base files, matching CLI behavior.
- **mkToggle race on agent pages** — rapid-toggle race condition on agents, plugins, and skills page toggles fixed.
- **Native confirm() replaced** — eager skill activation uses Evonic showConfirm() instead of browser's native confirm(), matching platform styling.
- **Browser autofill on search inputs** — autocomplete disabled on all search fields to prevent browser autofill from injecting unrelated values.
- **Continuation nudge disabled** — auto-continuation prompt injection deactivated to prevent unwanted agent behavior.
- **/summary accurate when summary unchanged** — slash command returns the correct message instead of a misleading error when nothing changed.
- **Missing clear_all_memories** — `/clear-memory` slash command now properly removes all memories instead of silently failing.
- **Contiguous per-session chat sequence** — sequence numbers contiguous per session, preventing SSE from seeing phantom gaps that triggered unnecessary re-fetches.
- **/summary AttributeError fix** — resolved `'AgentRuntime' has no attribute '_maybe_summarize'` crash.
- **Artifacts tools managed by feature toggle** — artifact-related tools controlled by the plugin feature toggle system instead of manual assignment.
- **Persistent 'Saved!' label replaced** — Tools tab uses disappearing toast notifications instead of a static label.
- **Path traversal escape in portal resolution** — path resolution hardened against directory traversal attacks escaping the portal root.
- **save_artifact error message improvements** — five fixes for unclear errors: missing filename, invalid filename, missing content, text-as-path misuse, and general exception context.
- **read_file directory error** — returns an actionable message when targeting a directory instead of a vague I/O exception.
- **Auto reply-back removed** — inter-agent auto-reply removed to prevent infinite ping-pong loops between agents.
- **str_replace/patch smart-quote robustness** — curly/smart double quotes in code no longer break str_replace and patch, especially for small models.
- **Flash-of-border on non-remote agent badge** — chat header badge no longer shows a brief border flash during initial render.
- **Lightbox window scope** — Lightbox exported to window scope so artifacts tab and non-chat views can invoke it.
- **SSE/polling leak on navigation** — SSE and polling connections properly closed on page navigation, preventing connection leaks.
- **Injection guard false positive** — base64-encoded file paths in CLI output no longer trigger the injection guard.
- **web_test bubble popup navigation** — notification bubble from web tests navigates to agent detail instead of sessions page.
- **Badge visibility for local agents** — workplace type badge resets className instead of using classList.add, fixing stale visibility state.
- **Stale runpy reference removed** — outdated descriptions referencing removed functionality cleaned from runpy tool documentation.
- **Enter-key on session reply input** — mobile/desktop Enter-key distinction now applies to session page reply input as well.
- **Kanban assignee blocked on done tasks** — completed and archived Kanban tasks can no longer have their assignee changed.
- **Auto-extraction from plan markdown removed** — task auto-extraction from plan markdown removed, fixing unintended task creation.
- **Early guard for missing file_path in read_file** — prevents AttributeError when `read_file` is called without a `file_path` argument.
- **Verbose lock debug removal** — `[LOCK] _llm_lock` debug logs silenced to reduce log noise.
- **Remove exa-py dependency** — unused exa-py removed from requirements.txt after exa-search skill migration.
- **Remove redundant artifacts injection** — duplicate artifacts SYSTEM.md injection removed from agents.py.
- **Replace Tailwind arbitrary classes** — arbitrary-value Tailwind classes replaced with inline CSS for more predictable thumbnail and lightbox styling.
- **Sidebar position:fixed** — sidebar positioning changed from CSS flex to `position:fixed`, preventing it from contributing to the flex container height and eliminating empty whitespace in the chat area.
- **Bypass is_skill_enabled in auto-assign** — `_exec_assign_skills` now bypasses the `is_skill_enabled()` gate when assigning tools, fixing an edge case where tools would silently fail to assign for newly-enabled skills.

## v0.6.78

145 commits

### New Features (13)

- **Agent Sidebar** — a persistent left sidebar showing agent avatars across all Evonic pages, with filtering, avatar images, toggle persistence via localStorage, and light/dark mode styling (#455). This gives you one-click access to any agent from anywhere in the platform, eliminating the need to navigate back to the agents page.
- **Message Wrapper Protocol** — every agent response now includes a structured wrapper with pre-response checks for memory storage and preference tracking. Configurable per-agent or globally, with automatic skip for short messages under 4 words (#465). This ensures your personal preferences, facts, and instructions are never missed across conversations.
- **Bubble UI Popup** — a notification bubble appears on the sidebar avatar when an agent sends a final response, with callout balloon styling and auto-suppression when you are already on that agent's page (#468). You will never miss a completed agent task while working elsewhere.
- **File & Image Upload in Agent Chat** — upload files and images directly in the agent detail chat interface (#490). No more switching to the sessions page just to attach a file to your conversation.
- **Audio & Video Multimodal Input** — agents can now process audio and video files as input for multimodal models. Extends the platform beyond text and images to handle voice recordings, video clips, and other rich media.
- **Semantic Memory Conflict Detection** — the memory system now automatically detects when a new memory contradicts an existing one, preventing inconsistent or conflicting facts from polluting your agent's knowledge over time.
- **Auto-Inject Agent Env Vars** — agent-specific environment variables are now automatically available in `bash` and `runpy` tool executions, with proper documentation in the system prompt. No manual export needed.
- **Health Endpoint** — a new `/health` endpoint reports database connectivity, disk space, and Docker container status (#61). Deployments can now integrate with uptime monitors and alerting systems.
- **Plugin Hot Reload** — plugins now reload automatically during development when source files change (#30). Plugin authors can iterate without restarting the server after every edit.
- **Outbound File Sending** — agents can now send files to Telegram and WhatsApp channels (#458). Your agents can deliver generated reports, images, or documents directly to your messaging apps.
- **Pre-Commit Safety Checks** — automated safety validation scripts for git commits (#493). Catches common issues before they reach the repository.
- **Clickable Plan Badge with Editor** — the plan badge in the Session State UI is now clickable, opening a full markdown editor modal where you can view and modify the active plan without leaving the page.
- **Skeleton Loading Placeholders** — the agent sidebar now shows animated skeleton placeholders while content loads, providing immediate visual feedback instead of blank space.

### Plugin's Features (1)

- **pinchtab_eval** — execute arbitrary JavaScript in browser tabs for advanced automation and evaluation scenarios (pinchtab plugin).

### Enhancements (41)

- **Thinking Bubble Auto-Expand/Collapse** — thinking bubble now auto-expands on message submit and auto-collapses when the turn completes (#494)
- **Evaluation Settings Tab** — new tab in system settings for configuring evaluator worker count (#488)
- **Sticky Fallback Model** — retry-aware persistence with intelligent context detection and dumb-truncation safety net, preventing infinite loops when fallback models are activated
- **Image/Vision Retry** — minimum 3x retry for image processing before falling back, with proper crash handling during model fallback (#480, #479)
- **Agent Model Columns Cleanup** — dropped legacy columns, renamed for consistency (#489)
- **Agents/Workplaces Tab Navigation** — standalone Workplaces page now has tab navigation between Agents and Workplaces (#484)
- **Schedule ID in Detail Modal** — schedule UUID now visible in the detail modal for easier reference (#483)
- **Confirmation Dialog for Non-Lazy Skills** — activating a skill that is not lazy-loaded now prompts a confirmation dialog (#481)
- **Auto-Inject Skill Cleanup Instruction** — all agent system prompts now include automatic skill load/unload cleanup rules (#469)
- **Eager Skill Tools Auto-Injection** — eagerly loaded skill tools are now auto-injected with skills_manager singleton reuse, eliminating redundant disk enumeration
- **Chat Input Enter-Key Behavior** — separate handling for mobile (newline by default) vs desktop (send by default) (#463)
- **Web Chat File Attachments** — file attachments displayed as downloadable cards in the web chat UI (#459)
- **Sidebar Agent Limit** — agent avatar list limited to max 15 entries for cleaner UI
- **Skill Unload Icon** — unload (X) icon added to skill badges in Session State UI (#457)
- **Fallback Model Reset Icon** — reset icon added to fallback model badge in Agent State UI (#456)
- **Sidebar Toggle Alignment** — toggle button width aligned to 64px to match sidebar width
- **Sub-Agents Force Execute Mode** — sub-agents now start in execute mode by default, reducing plan/execute friction
- **Evaluator Two-Pass Extraction** — exposed in UI and docs (#38)
- **Full-Stack Developer Skillset** — new pre-configured skillset template for full-stack development agents
- **PinchTab Evaluate Auto-Enable** — evaluate endpoint auto-enabled when disabled
- **PinchTab Occluded Element Guidance** — agents now receive hints for handling occluded elements and stale references
- **Tool JSON Definitions Cache** — cached with mtime invalidation, eliminating repeated JSON serialization (#474)
- **reencode_unicode_escapes Optimization** — list lookup + isascii fast path for unicode normalization (#471)
- **Evaluator Parallelization** — domain-level tests run in parallel with sleep removed (#475)
- **Compiled Regex Patterns** — regex compiled at module level in sql_executor for faster repeated matching (#477)
- **O(log N) Event Boundary Lookup** — bisect-based boundary search in get_events_in_range (#478)
- **LLM Client Settings Cache** — context_length, prompt_buffer, max_retries cached with 30s TTL (#472)
- **Skills mtime Hash Cache** — avoids re-enumerating skill files from disk on every query (#473)
- **Agent Config Cache** — agent config cached in run_tool_loop to avoid redundant DB reads (#476)
- **Session Index Elimination** — cross-DB ATTACH/UNION ALL removed for session aggregation (#460)
- **Dashboard Query Optimization** — connection reuse, SQL pushdown, correlated subquery fix (#461)
- **Lazy Migration + PRAGMA** — lazy migration, removed redundant polling, SQLite URI PRAGMA optimization (#462)
- **KB Frontmatter in System Prompt** — KB frontmatter description requirement documented in system prompt
- **/_self/artifacts/ Virtual Path** — new virtual path alias for agent artifacts directory (#419)
- **Safety Toggles Moved** — Safety Checker and Injection Guard toggles relocated to Advanced Settings (#399)
- **Toast Notifications** — improved toast system with button re-enable and robust error parser (#395)
- **Model Test Connection Feedback** — loading spinner, success/error states with icons (#395)
- **Download UI Consolidation** — URL and button merged into one row, curl hint removed
- **Auto-Scroll Log View** — dark green color scheme with auto-scroll to bottom (#394)
- **Evonet Tunnel Awareness** — system prompt dynamically aware of Evonet tunnel workplaces
- **README Update** — CLI commands corrected, missing features documented, architecture diagram improved

### Bug Fixes (39)

- **`[Image]` Placeholder for Image-Only Messages** — chat now displays `[Image]` placeholder instead of empty messages for image-only responses
- **Gemma4-12B Bold Markdown Spacing** — fixed extra space after `**` in bold markdown output via post-processing regex anchored with negative lookbehind to avoid eating the space after closing bold markers, applied in both `llm_client.py` and `gemma4_parser.py`
- **Kanban Task ID Type Mismatch** — task_id normalized to string to prevent comparison bugs (#51)
- **Unreplied Chat Session Resume** — unreplied chat sessions now resume properly on server startup
- **Plugin Settings Attribute Error** — replaced non-existent `_plugins` attr with `list_plugins()` in agent plugin settings
- **Absolute Path Resolution** — `resolvePath` now handles absolute paths correctly
- **Slash Command Response Display** — slash command responses now appear immediately in sessions chat UI
- **`.env` File Permission Warning** — warns about insecure `.env` permissions when SECRET_KEY is auto-generated (#60)
- **Shallow Clone Remote Fetch** — install.sh reconfigures remote fetch after shallow clone to track branches (#59)
- **Thinking Budget Cast** — added `int()` defensive cast for thinking_budget in model config (#492)
- **/_self/ Path Resolution** — fixed eager SYSTEM.md migration and sub-agent effective ID handling
- **`[DONE]` Frontend Leak** — suppressed `[DONE]` from llm_response_chunk to prevent leaking into the UI
- **Multimodal Content in Wrapper Prefix** — `_apply_wrapper_prefix` now handles multimodal content (list type)
- **Scheduler Silent Message Drop** — fixed silently dropped messages with embedded routing info at creation (#487)
- **Scheduler Timezone Awareness** — bare run_date strings now properly timezone-aware (#486)
- **Sidebar Height on Mobile** — auto height on mobile to eliminate blank space (#485)
- **Workplace DB CHECK Constraint** — 'tunnel' type no longer rejected as invalid (#54, #482)
- **Plan Editor Modal Layout** — fixed height and textarea flex layout in agent detail (#418)
- **Read/Read_File Token Compression Exclusion** — these tools correctly excluded from token compression per user preference
- **KB Frontmatter Mandatory** — KB files now require frontmatter in agent instructions
- **Skeleton Placeholder Dark Mode** — fixed invisible skeleton placeholders with bg-gray-400 fallback (#466)
- **Plan Editor Event Listeners** — wrapped in DOMContentLoaded to prevent null element errors
- **Tomli Fallback** — added tomli fallback for tomllib on Python < 3.11
- **Context-Exceeded Retry Guard** — llm_error retry now guards against context-exceeded errors
- **Sub-Agent Chat History** — sessions page now renders sub-agent chat history readably
- **Unreplied-Chat Scan Scope** — startup scan limited to human-facing sessions (#32)
- **File I/O Routing** — file I/O tools routed through workplace backend even when sandbox is disabled (#464)
- **SSE Response Bubble** — final response bubble now renders synchronously from SSE stream
- **Dead TONES Lookup** — removed dead TONES lookup that broke Next on Super Agent setup step (#50)
- **Python 3.9 Compatibility** — PEP 604 union types (`str | None`) replaced with `Optional[str]`
- **SVG Avatar XSS Prevention** — SVG avatar uploads rejected to prevent stored XSS (#52)
- **Heredoc stdin Rebind** — stdin rebound to /dev/tty in pass_setup() for heredoc compatibility
- **Sidebar Light-Mode Styling** — fixed styling issues in sidebar light mode (#455)
- **Remote/Tunnel Workplace Check** — local filesystem workspace check skipped for remote/tunnel workplaces (#432)
- **Root Project Update** — fetch+reset replaces pull --ff-only for more reliable updates
- **Same-Version Update Block** — blocked redundant same-version updates with daemon crash log surface
- **Evaluator Sandbox** — mock test runner sandboxed with AST validation (#46)
- **Template File Allowlist** — `.env.example` template files correctly allowlisted for read_file access
- **Audio OGG-to-WAV Conversion** — Telegram and WhatsApp voice messages (OGG/Opus) are now automatically converted to WAV before being sent to multimodal LLM APIs that only support WAV/MP3 input formats. Includes graceful degradation when ffmpeg is unavailable (#500)

## v0.5.24

24 commits

### Enhancements (11)

- **Injection Guard toggle** — enable/disable Injection Guard per-agent with a simple toggle in Advanced Settings (#397)
- **Recall tool result contents in thinking bubble** — tool result contents visible directly inside the thinking bubble for easier context tracking (#398)
- **Auto-scroll + dark green log view** — log viewer now auto-scrolls to bottom with a dark green color scheme (#394)
- **Evonet tunnel workplace awareness** — system prompt now includes workspace information when using Evonet tunnels
- **`/_self/artifacts/` virtual path** — new virtual path alias for agent artifacts directory accessible via file tools (#419)
- **Plan badge clickable modal** — clicking the plan badge in session view opens a modal with full plan details (#418)
- **Safety/Injection Guard toggles moved to Advanced Settings** — relocated toggles from top-level to Advanced Settings section (#399)
- **Toast notifications + robust error parser** — improved toast notification system with a more robust error message parser (#395)
- **Model test connection visual feedback** — test connection button now provides clear visual feedback during model testing (#395)
- **Download URL/button merged into one row** — consolidated download URL and button into a single row for cleaner UI
- **Removed curl sample hint** — removed the curl example hint from the download section

### Bug Fixes (11)

- **UnboundLocalError on lazy skill unload** — fixed variable reference error when unloading skills that were never loaded
- **Approval modal 409 stuck** — fixed approval modal getting stuck on HTTP 409 conflict responses
- **`.env.example` read access denied** — fixed file read access error when accessing `.env.example`
- **Summarizer JSON template crash** — fixed crash caused by invalid JSON template processing in the summarizer
- **SSE thinking spinner stuck** — fixed thinking spinner getting stuck during Server-Sent Events streaming
- **Stale symlink false update banner** — fixed false "update available" banner caused by stale symlink references
- **[DONE] response content recovery** — recovered response content that was lost after [DONE] signal in streaming
- **Plan files per-agent sandbox path** — fixed plan file paths to use per-agent sandbox paths instead of shared paths
- **False positive `git add .gitignore`** — fixed false positive detection in git operations involving `.gitignore`
- **`str_replace` unicode escape mismatch** — fixed unicode escape sequence handling in str_replace tool
- **Update race guard + timeout** — added race condition guard and timeout to the update manager

## v0.5.0

255 commits

### New Features (11)

- **Agent Artifacts** - persistent file output system with `save_artifact` tool, artifact modal viewer, `read_attachment` tool with cross-agent isolation, delete endpoint with auth check, and attachment cleanup on session delete
- **RTK Token Compressor** - 8-stage modular compression pipeline with TOML schema, Python and Rust builtin filters, agent-specific and project-level filter overrides via KB, token savings tracking API (`/api/rtk/gain`), config knobs (`RTK_NO_COMPRESS`, `RTK_VERBOSE`), and safety net fallback
- **Thinking Budget Cap** - per-model round-based budget enforcement for small model efficiency (Phase 2)
- **Quality Monitor with Auto-Correction** - automatic correction and output parser for improved response quality
- **Long-running command guardrail** - detects build/compile commands and suggests tmux/screen alternatives
- **`/exec` slash command** - switch agent mode from plan to execute directly via chat
- **`forget_memory` tool** - long-term memory deletion for soft-deleting stale or irrelevant memories
- **`assign_skills` / `unassign_skill` super-agent tools** - assign and remove skills from agents programmatically
- **Evonic Backup System** - CLI-based backup, restore, and verification with `evonic backup` command (`evonic-backup-[YYYYMMDD]-[HHMM].tar.gz` naming format)
- **File upload in web chat UI** - upload files directly from the chat interface
- **Per-agent model fallback** - configurable fallback chain with 1 retry, persistence across sessions, and UI badge indicator

### Plugin’s Features (2)

- **Model-router plugin** - per-model base system prompts (`SYSTEM_PROMPTS`), model list endpoint, and token widget UI overhaul (model-router plugin)
- **Plugin widget mechanism** - auto-load `*_widget.html` in plugin detail page for custom UI

### Enhancements (53)

- **Search bars on /plugins and /skills pages** - client-side filtering for quick navigation (#362, #365)
- **Compact plugin and skill cards** - redesigned to match /agents card pattern with compact layout (#361, #364)
- **Token list SVG icons** - replaced text Edit/Delete buttons with SVG icons in API token list (#333)
- **Test Model feedback modal** - loading spinner, success/error states with icons, dark mode support (#371)
- **`/model` command simplification** - removed model UUID from output, formatted list as Markdown (#372)
- **Prompt-only skill badges** - show skills without tools as badges with divider line between Tasks and Skills
- **State API with loaded skills** - `/api/state` now exposes `loaded_skills` with skill badges rendered in sessions page (#359)
- **SSE bridge state-change trigger** - add `use_skill`/`unload_skill` to SSE state-change trigger list (#358)
- **Remove `Regular` category badge** - removed from non-system plugin cards (Robin feedback)
- **User-directory plugin UI refactor** - migrated to evonic standard styling with profile section cleanup (#331)
- **Evonet GUI improvements** - Clear button in toolbar (#343), version number in window title, FyneApp.toml for macOS metadata
- **Translate remaining Indonesian to English** - all Indonesian copy in `cli/commands.py` translated (#342)
- **Backup file format** - standardized naming to `evonic-backup-[YYYYMMDD]-[HHMM].tar.gz` (#341)
- **`send_agent_message` focus mode guard** - reject message when target agent is in focus mode
- **Script placement rule** - all scripts must be in `scripts/` directory; migrations in `scripts/migrations/`
- **Smart quote normalization** - `normalize_code_quotes` replaces smart quotes with ASCII equivalents in `str_replace` and `patch`
- **Remove TONE_PRESETS mechanism** - replaced with `{communication_style}` placeholder in super agent prompt template
- **Add `tmux` to tools Dockerfile** - added for long-running command execution support
- **Long-running guard error message** - inline run script into error message for weaker models
- **Upload evonic helpers to SSH** - auto-upload evonic helpers to remote SSH host on first `run_python` call
- **`nohup` PID file fallback** - nohup fallback now saves PID to file for cross-session tracking
- **Migration scripts cleanup** - moved all migration scripts to `scripts/migrations/`
- **Remove `_scripts/` directory** - consolidated into `scripts/`
- **Auto-load all skill tools for super agent** - skills auto-loaded for super agent; fix scheduler config type handling
- **Get version from GitHub Releases API** - instead of local git tags for more reliable update detection
- **Make `patch` handle JSON `\\uXXXX` escapes** - handles LLM double-escaping and JSON unicode escapes in context matching
- **`portal_copy` tool** - binary file transfer between workspaces and portals
- **Treat code files as plain text** - in artifacts explorer for better inline preview (#312)
- **Improve `read_attachment` tool** - with file parsing, access checks, and cross-agent isolation
- **Delete attachments on session clear** - purge files on session delete and clear-all sessions
- **Add `gh` CLI installation guide** - comprehensive guide for all OS in GitHub skill KB
- **Add EVONIC_BANNER refactor** - deduplicate banner, import from `cli.commands`
- **Structured logging for agent_messaging** - add agent_messaging tool inclusion in agent log routes

- **Intent-based Skill Injection** - dynamic tool guidance by injecting relevant skill context based on agent intent
- **Write-vs-Edit guard** - `write_file` now refuses to overwrite existing files, guiding agents to use `str_replace` or `patch` for surgical edits
- **Improved `patch` tool** - tiered fuzzy matching with exact, indent-tolerant, and unescape-tolerant fallback tiers
- **Process tracker** - immediate `/stop` interrupt for running tool executions via PID-based process tracking
- **Dynamic edit tool suggestion** - writes overwrite guard dynamically suggests the best edit tool based on agent's assigned tools
- **Channel user identity injection** - inject channel user identity into agent context for personalized responses
- **Dynamic enabled-agent roster injection** - inject live list of enabled agents into super agent system prompt
- **Cloud \u2192 Tunnel rename** - full rename across DB schema, migration, routes, config, templates, tests, KB files, and README
- **Scheduler `session_prompt` action type** - trigger full LLM sessions from scheduled jobs with tool access
- **Scheduler detail modal** - display `static_message` content in scheduler detail view
- **Improve `webhook` input filter** - per-event-type JSON filter configuration for webhook payloads
- **Sanitize Docker/container language** - remove container terminology from tool descriptions for non-sandbox agents
- **Telegram username allowlist** - enhance Telegram user allowlist to include username-based filtering
- **Accurate tiktoken token counts** - compiled context now shows memories and summary with precise token counts
- **Extract user-directory plugin** - moved user-directory plugin to its own independent git repository
### Bug Fixes (44)

- **False-positive continuation nudge** - fixed on report-style responses, completion/summary responses, and permission-seeking responses (sessions 67fd3ea1, 25ac767d)
- **Continuation nudge negation fix** - `PLANNING_RE` nudge negation broke out of loop instead of falling through
- **Spaced character evasion false positive** - fixed false positive on normal words
- **Safety pipeline import graceful fallback** - all tool files (`bash.py`, `patch.py`, `str_replace.py`, `write_file.py`) now wrap `safety_pipeline` import in try/except with warning log and graceful degradation
- **`_skip_safety` flag hardening** - requires strict boolean `True` to skip safety checks
- **Kanban `tool_guard` self-heal** - clears stale pending status for done/reassigned tasks
- **Dark mode UI fixes** - hover text on Advanced Settings button (#352), hover styling for session items (#360), fix dark mode for user-directory plugin modals and table
- **EvoNET build fix** - fixed evonet build and `portal_copy` for absolute paths
- **Old CHECK constraint migration** - handle old CHECK constraint during cloud-to-tunnel workplace migration
- **`/clear` chat input fix** - clear chat input after `/clear` command submission (#392)
- **Task text sanitization** - prevent inconsistent status indicator rendering from sanitized task text
- **Loaded skill badge persistence** - clear in-memory `_session_skill_mds`/`_session_skill_tools` in slash command handler (#373)
- **Add `from __future__ import annotations`** - for Python 3.9 compatibility
- **Max_lines zero head/tail** - fix max_lines=0 behavior in token compressor
- **`ls -la` regex fix** - handle `ls -la` output in token compressor filter
- **`git add` empty-input** - handle empty input in git add operations
- **False-positive SSH path detection** - fix false positive for normal paths containing `.ssh`
- **Artifact CSS fix** - missing `group-hover:opacity-100` CSS rule for artifact action buttons (#344)
- **Replace native `confirm()` with `showConfirm()`** - in `deleteArtifact()` for consistent UI (#344)
- **Fix misleading `Execution stopped by user`** - for sudo/signal deaths that were not user-initiated
- **`/help` command visibility** - fix `/help` showing `/cd` and `/cwd` commands to non-super agents
- **Auto-detect task completion status** - from embedded markers in text
- **Tool date booking L3 test fix**
- **Fix smart quote in `showTab()`** - replaced smart quote with regular quote
- **Use Jinja `{{ plugin_id }}`** - instead of global `PLUGIN_ID` in widget scripts
- **Fix `spaced_character_evasion` rule** - false positive on normal words
- **Fix nohup fallback** - PID file for cross-session tracking
- **Update token compressor filters** - fix filters for ls command
- **Fix agent detail Advanced Settings** - dark mode hover text
- **Fix eval page real-time logs** - escape HTML in Real-Time Logs (#335)
- **Fix session state task list display** - not shown in chat UI right panel (#226)
- **Fix `renderAgentState`** - now passes `session_id` and renders task list correctly (#226)
- **Fix portal Add button** - 6 JavaScript/HTML ID mismatches causing silent failure
- **Forward sub-agent replies to parent agent** - ensure replies reach correct session
- **Fix `escalate_to_user`** - deliver messages to both channel and web sessions
- **Fix slash command interception** - in `send_as_user` and scheduler routing for real users
- **Fix session persistence for mobile web** - ensure mobile chat state survives navigations
- **Fix trailing newline in patch.py** - when no lines remain after patch application
- **Fix normalize curly quotes** - in SQL answer extraction for reliable parsing
- **Fix restart ready message** - proper web chat thinking bubble for slash commands
- **Show webhook secret as plain text** - instead of masked for copy-paste (#212)
- **Fix missing build script** - chat-ui.js not regenerated after changes
- **Re-route SSE adapter after turn_split** - maintain real-time updates in monolith mode
- **Update progress persistence** - survive crashes during update with progress tracking and pre-flight checks


## v0.3.43

24 commits

### Enhancements (9)

- **Auto-refresh after saving valid workspace directory** (#232)
- **Migrate Tailwind Play CDN to pre-compiled CSS build** (#235)
- **Remove redundant CSS reset in style.css** (#235 follow-up)
- **Add divider between session list items in chat room sidebar** (#236)
- **Add `!important` to divider border to beat Tailwind CDN preflight reset** (#236)
- **Reposition lazy badge to right of skill name in skill card** (#230)
- **Refactor CLI** — deduplicate `EVONIC_BANNER`, import from `cli.commands`
- **Update ASCII art**
- **Docs: update AgentAPI README** — session behavior clarification

### Plugin’s Features (1)

- **AgentAPI stateless by default, opt-in stateful via `X-Session-Id`** (AgentAPI plugin)

### Bug Fixes (9)

- **Drop orphaned and duplicate tool messages from reconstructed context**
- **Guard JSONL history rebuild when prefetch cache is used**
- **Count semantic messages for JSONL tail scan limit, not raw entries**
- **Authorize lazy skill tools** — update `assigned_tool_ids` on load/unload/restore
- **AgentAPI plugin: treat system message as user message**
- **Inject synthetic tool responses for interrupted tool calls in history**
- **Add authorization guard in `real_executor`** — block unassigned tools
- **Fix(#277): use single braces for `current_datetime` in `DEFAULT_SUMMARIZE_PROMPT`**
- **Fix(#229): remove stale evonic shell helper references**


## v0.3.19

113 commits

### New Features (2)

- **Portal feature** — virtual path mapping for agent file I/O, enabling external filesystem access through agent tools
- **recall_sessions built-in tool** — query session summaries from database with keyword search

### Plugin's Features (2)

- **Webhook input filter** — per-event-type JSON filter configuration for webhook payloads (Github Webhook plugin).
- **AgentAPI token management UI** — create, edit, delete, and inspect API tokens for agent access (AgentAPI plugin).

### Enhancements (13)

- **Session State** — migrate mode/plan_file/tasks from Agent State to a dedicated Session State; rename Session Recap to Session State with mode badge and task/plan file display
- **Skill briefs and lazy/eager guard** — skill descriptions with load behavior control and visual badges
- **Lazy badge on skill cards** — visually indicate which skills use lazy tool loading
- **Stale sandbox cleaner** — robust cleanup of orphaned containers with clear-sandbox CLI command
- **Sandbox awareness injection** — inject sandbox environment notice into agent system prompt
- **Show skill ID in skills page card list** — display skill identifier alongside name (#213)
- **Render task text as markdown** — in Session State panel for rich formatting
- **Update navbar logo** — use mascot.png for improved branding (#208)
- **Structured logging** — add agent_messaging tool inclusion in agent log routes
- **Add LICENSE (AGPL-3.0) and COMMERCIAL.md** — clear licensing with commercial terms
- **Simplify sandbox naming** — use evonic-<session-id> pattern (#227)
- **Plugin export/import (.evop)** — package and distribute plugins as portable archive files
- **Push notification system** — proactive push notifications to users via scheduler with period/channel configuration

### Bug Fixes (28)

- **Inject current date/time into summarization prompt** — prevents LLM date hallucination in session summaries
- **Security audit fixes** — resolve C-1, C-2, M-4, M-6, M-7, H-5 findings from production readiness audit
- **Add .env file protection to file operation tools** — prevent credential leaks via read_file/write_file
- **Security: path traversal in skill installation** — prevent arbitrary file overwrite during install
- **Security: command injection in update manager** — prevent code injection via crafted version strings
- **Security: improve version comparison** — handle pre-release versions safely with backward compatibility
- **Ensure ~/.evonic is on main branch** — after clone/update operations to prevent detached HEAD
- **Preserve unsummarized assistant context** — in conversation tail for session continuity
- **Fix infinite loop from empty PLANNING_RE** — missing nudge counter increment caused runaway loop
- **Resolve 7 audit-identified bugs** — in runtime, llm_loop, and context subsystems
- **Fix thinking bubble position and LLM loop continuation** — various rendering state bugs
- **Fix session state task list display** — not shown in chat UI right panel (#226)
- **Fix renderAgentState** — now passes session_id and renders task list correctly (#226)
- **Make evonic importable in non-sandbox mode** — fix runpy import path (#228)
- **Fix portal Add button** — 6 JavaScript/HTML ID mismatches causing silent failure
- **Forward sub-agent replies to parent agent** — ensure replies reach correct session
- **Remove model UUID from /model output** — when called without args (#205)
- **Fix escalate_to_user** — deliver messages to both channel and web sessions
- **Add dark mode support** — for agent state UI text and evaluation conversation blocks (#209)
- **Fix slash command interception** — in send_as_user and scheduler routing for real users
- **Fix session persistence for mobile web** — ensure mobile chat state survives navigations
- **Fix trailing newline in patch.py** — when no lines remain after patch application
- **Fix normalize curly quotes to ASCII** — in SQL answer extraction for reliable parsing
- **Fix restart ready message** — proper web chat thinking bubble for slash commands
- **Show webhook secret as plain text** — instead of masked for copy-paste (#212)
- **Fix missing build script** — chat-ui.js not regenerated after changes
- **Re-route SSE adapter after turn_split** — maintain real-time updates in monolith mode
- **Update progress persistence** — survive crashes during update with progress tracking and pre-flight checks


## v0.2.6

126 commits

### New Features (4)

- **Sub-agent system** — ad-hoc sub-agent spawn/destroy/list via dedicated skill with SubAgentManager singleton; sub-agents inherit parent's SYSTEM.md, KB, tools, and skills; session visibility, lifecycle cleanup, and parent-only messaging
- **/status slash command** — displays agent state info including model, description, tool count, and channel count (#159)
- **Update available notification system** — real-time progress UI with current-to-latest version display and auto-triggered status check
- **Clone model** — duplicate existing model configurations (#153)

### Enhancements (26)

- **Task complexity classifier** — automatically skips planning phase for trivial tasks to reduce latency
- **3-column agent selector modal** — revamped with avatar display and auto-select on click (#186)
- **Evaluation summary dark mode** — properly styled for dark theme (#150)
- **Chat input draft persistence** — saves draft in localStorage across page navigations (#157)
- **Optimistic comment append** — instant UI feedback with loading state on submit button (#156)
- **Model card action buttons** — changed from vertical stack to horizontal row positioned at right-bottom (#198)
- **/status output format** — separated Telegram vs web output format for better readability (task #200)
- **Remove Active badge from agent card** — cleans up agent card item UI (#188)
- **Delete interrupted evaluations** — interrupted/canceled evaluations are cleaned up immediately (#187)
- **GUI connection status** — updates status text after successful WebSocket connection (#158)
- **Left padding on "Connected." text** — via `NewPadded` for consistent alignment (task #158)
- **SECRET_KEY auto-generation during setup** — generated persistently during setup flow (#162)
- **.env file safety check** — `read_file` tool now checks for .env access to prevent credential leaks
- **Console log noise reduction** — suppresses `apscheduler.*` logs via `EVONIC_LOG_CONSOLE_QUIET` setting
- **install.sh now auto-detects latest stable release** — fetches latest tagged release for fresh installs instead of hardcoded version (#67)
- **Qwen XML tool call parsing** — adds support for Qwen-style XML tool call format in LLM client and evaluator
- **Agent Queue Workers setting** — configurable in system settings UI with DB-backed persistence (#169)
- **Max tool iterations setting** — configurable in web UI with DB-backed persistence (#169)
- **Manual save for non-toggle settings** — settings that don't use a toggle now have explicit Save button (#173)
- **About modal** — displays version, description, creator, and community links (#160)
- **User approval for inter-agent restart** — require explicit approval before one agent restarts another (#171)
- **Search bar in Workspaces page** — filter workspaces by name (#155)
- **Session ID in /status** — shows current session ID in slash command output (#192)
- **Allow partial assignee in Kanban** — empty assignee allowed in Assign Agents modal for partial assignment (#191)
- **Telegram channel pairing** — LLM extracts user name from introduction message during pairing flow
- **Kanban comment tool** — `kanban_get_comments` tool with pagination support (task #161)

### Bug Fixes (48)

- **Disable DEBUG mode by default** — fixes CVE risk of detailed error disclosure in production (#85)
- **Hard-fail when SECRET_KEY is missing** — removes `.secret_key` fallback to prevent insecure defaults (#162)
- **Auto-generate persistent SECRET_KEY** — removes hardcoded default, generates random secret on first run (#162)
- **Read SECRET_KEY from .env** — fallback to prevent key regeneration on restart
- **Do not write empty api_key if not set** — prevents overwriting existing API key with empty value
- **Atomic write in `_update_env_var`** — prevents partial .env corruption on crash (#164)
- **Systemic file descriptor and database leaks resolved** — closes file handles and database connections properly (#11)
- **Handle `None` metadata in restart_handler** — prevents crash when context builder returns no metadata (#166)
- **Sub-agent TTL expiry during active LLM loop** — prevents premature sub-agent destruction while LLM is still streaming
- **Sub-agent nesting prevented** — enforces max 10 sub-agents per parent and prevents recursive spawning
- **Sub-agents restricted to parent-only messaging** — sub-agents can no longer message arbitrary agents
- **Sub-agent session visibility** — sessions now appear correctly on Sessions page
- **Sub-agent tool ID and memory fixes** — runtime fixes for tool ID resolution, variable passing, and log path
- **Sub-agent report-back and lifecycle cleanup** — ensures proper cleanup on sub-agent destruction
- **`/cd` slash command not taking effect** — caused by prefetcher not validating directory change
- **Enable parallel sub-agent execution** — fixes blocking behavior that serialized sub-agent runs
- **Telegram re-add chat error** — fixes issue where removing and re-adding a Telegram chat caused prompt mismatch
- **Restart greeting sends static reply via channel** — prevents LLM-generated greeting after `/restart`
- **Filter slash command messages from LLM context** — prevents re-processing of slash command output as user input
- **Skip restart greeting when using `/restart`** — avoids duplicate greeting on intentional restart
- **Fix user messages interleaved between tool responses** — `_fix_interleaved_user_messages` handles edge cases correctly
- **Anchor slash command response after user message during active stream** — prevents slash responses overwriting stream content
- **Prevent duplicate thinking bubble on page load** — fixes race condition in chat-UI (#149)
- **Re-route SSE adapter to new turn after turn_split** — prevents stale SSE connection on conversation split
- **`/status` now uses agent model settings** — and fixes one-line markdown rendering in channel output (#159)
- **Summary generation failure** — wrong argument passed to `extract_content` in evaluator (#149)
- **Restore bullet points in Plugin Detail About tab** — formatting regression (#168)
- **Swap Logs and HMADS tabs in system settings** — incorrect tab ordering (#152)
- **Show enabled agents only in kanban assignment dropdown** — excludes disabled agents (#154)
- **Optimistic comment append wipes previous comments** — comment list replaced instead of appended (#156)
- **Select theme settings** — theme selection now persists correctly
- **Explicit `stream: false` in OpenAI-compatible payload** — prevents streaming issues with some providers (#8)
- **Use semver comparison for update availability** — fixes incorrect update detection with pre-release versions
- **Move model card action buttons to right side** — positioning fix (#198)
- **Display `file_path` in safety approval dialog** — shows which file is being accessed (#197)
- **Heuristic safety: reduce SQL false positives** — better pattern matching for destructive SQL detection
- **Release-mode path resolution and start parity** — ensures dev and release modes behave identically (#10)
- **Persist daemon PID for status/stop after upgrade** — daemon PID file survives upgrade process
- **Test mocks return proper defaults** — fixes `max_tool_iterations` default in test mocks
- **`fix(evalutor): summary generation always fails`** — wrong arg passed to `extract_content`
- **`fix(#148): read() KB tool path resolution`** — use `os.path.abspath(__file__)` for reliable base directory
- **`fix(#148): read() tool description for remote vs local`** — tailored description for each context
- **`fix(#148): add /_self/ path handling`** — ensures `/_self/` prefix works correctly in KB tool
- **`fix: remove duplicate _is_safe_redirect_url`** — and correct weekend logic in `check_price`
- **`fix(evonet): enable cross-compilation`** — macOS/Windows builds from Linux now work

