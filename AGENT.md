# SmartChatBot Project Notes

## Current Progress (2026-06-05)
- Project skeleton created under `/root/workspace/smart-chatbot/`
- venv created at `/root/workspace/smart-chatbot/venv/` with all deps installed
- opencode config set: `/root/workspace/opencode.json` with `permission: "allow"` (requires restart)

## Architecture
- Backend: FastAPI + psycopg2 → openGauss (Docker)
- Frontend: Single HTML/JS file (no framework)
- PII Detection: Microsoft Presidio
- LLM: DeepSeek API (OpenAI-compatible, only receives sanitized content)

## Key Files
- `docker-compose.yml` — openGauss service with TDE + audit
- `db/init.sql` — Schema with TDE config, encrypted columns, audit setup
- `backend/main.py` — FastAPI routes (register, login, chat, conversations, audit-logs)
- `backend/auth.py` — JWT authentication + bcrypt password hashing
- `backend/pii_redactor.py` — Presidio PII detection and redaction
- `backend/llm.py` — DeepSeek API client (only gets sanitized_content, not raw PII)
- `backend/audit.py` — Audit log writer to openGauss
- `backend/config.py` — Config with DB, JWT, and DeepSeek settings
- `frontend/index.html` — Chat UI + Audit Log panel + PII toggle
- `deploy/nginx.conf` — Nginx config for cross-host access

## Chat Flow (with LLM)
```
user input → PII redact → store raw+sanitized in openGauss → audit log
  → LLM(sanitized_content only) → store response → audit log → return
```

## Deployment
- Frontend via Nginx on port 80 (public IP: 8.163.89.73)
- Backend via uvicorn on port 8000 (proxied by nginx `/api/`)
- openGauss via Docker on port 5432

## Remaining Tasks (execution was interrupted)
1. Enable nginx site and start it:
   ```bash
   ln -sf /root/workspace/smart-chatbot/deploy/nginx.conf /etc/nginx/sites-enabled/smart-chatbot
   rm -f /etc/nginx/sites-enabled/default
   nginx -t && systemctl restart nginx
   ```
2. Start openGauss: `docker compose up -d` (in smart-chatbot dir)
3. Start backend: `cd /root/workspace/smart-chatbot && source venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
4. Verify: visit http://8.163.89.73 in browser, register + send a message
5. Optional: set `DEEPSEEK_API_KEY` env var for LLM integration
