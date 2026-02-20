# OpenClaw Memory Add-on — Implementation Report

Generated: 2026-02-20

Source project: https://github.com/mdkrush/openclaw-jarvis-memory.git

## Summary (what it does)
This project adds “Jarvis-like” persistent memory to OpenClaw via a 3-layer architecture:

1) **Redis short-term buffer**
- Captures user/assistant text into Redis list keys like `mem:<user_id>`.
- Two capture methods:
  - Heartbeat capture (append turns using a turn counter).
  - **Token-free cron capture** (reads OpenClaw session `.jsonl` files directly and tracks byte offsets) → avoids LLM calls.

2) **Daily markdown logs**
- Blueprint expects `workspace/memory/YYYY-MM-DD.md` for human audit.
- Some scripts exist but at least one is not portable as-written (hardcoded `/root/...` + fixed LAN IPs).

3) **Qdrant long-term semantic memory**
- Stores vectors in Qdrant collection (default `kimi_memories`).
- Embeddings via **Ollama** (`snowflake-arctic-embed2`).
- Dedup via `sha256(user_msg::ai_response)` stored in payload.

Retrieval is done by embedding the query and searching Qdrant; usage can update access counts.

## Compatibility with our current VPS
This can work, but must be adapted to our actual paths:
- Workspace: `/data/.openclaw/workspace` (not `~/.openclaw/workspace`)
- Sessions dir: likely under `/data/.openclaw/agents/<agent>/sessions` (confirm exact)

Some scripts are hardcoded to `/root` paths and private LAN IPs and should not be run unchanged.

## Implementation plan (safe / explicit)
### Phase A — Decide deployment model
- Recommended: run **Redis + Qdrant + Ollama** via Docker on the VPS host.
- Capture strategy: **cron_capture.py every 5 min** (token-free) + daily `cron_backup.py`.

### Phase B — Bring up services
- Use docker-compose, but bind ports to **localhost only**:
  - `127.0.0.1:6379` (Redis)
  - `127.0.0.1:6333` (Qdrant)
  - `127.0.0.1:11434` (Ollama)
- Ensure persistent volumes.
- Pull embeddings model (`snowflake-arctic-embed2`).

### Phase C — Configure env paths
Create a config file (example):

```bash
OPENCLAW_WORKSPACE=/data/.openclaw/workspace
OPENCLAW_SESSIONS_DIR=/data/.openclaw/agents/main/sessions
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
QDRANT_URL=http://127.0.0.1:6333
OLLAMA_URL=http://127.0.0.1:11434/v1
USER_ID=<your persistent user id>
```

### Phase D — Initialize Qdrant collection
- Create collection and verify insert/search.

### Phase E — Enable automation
- Every 5 minutes: token-free capture reads new `.jsonl` bytes and appends to Redis.
- Daily: backup job writes turns into Qdrant and clears Redis only if successful.

### Phase F — Retrieval integration
Decide whether memory retrieval is:
- Manual commands first (safer), or
- Automatic injection at session start (more seamless; higher risk of irrelevant context).

## Security / privacy
- You are storing full conversation text → consider redaction and retention policy.
- Redis/Qdrant are unauthenticated by default → bind to localhost + firewall; consider auth/TLS.
- Backups/logs can contain sensitive data → lock down permissions; avoid public storage.

## What you need to provide
1) Confirm exact sessions path on this VPS.
2) Decide scope (which chats/sessions to store) and a `USER_ID` scheme.
3) Confirm whether we can run Docker services on the host (or provide hosted endpoints).

## Rollback plan
- Disable cron/systemd timers.
- `docker compose down` (volumes retained) or delete volumes only if you explicitly want to erase memory.
- Remove added scripts/config.

## Notes
The repo is best treated as a **blueprint + scripts**. The biggest gotchas are (a) hardcoded paths/IPs in some backup scripts, and (b) security (unauthenticated vector store with sensitive text).
