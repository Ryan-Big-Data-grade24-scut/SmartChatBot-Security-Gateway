from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from auth import hash_password, verify_password, create_access_token, get_current_user
from database import get_cursor
from pii_redactor import detect_and_redact
from injection_detector import detect_injection
from audit import log_action
from llm import chat_with_llm, build_conversation_context
from config import (
    LLM_ENABLED,
    INJECTION_DETECTION_ENABLED,
    RATE_LIMIT_PER_USER,
    RATE_LIMIT_PER_IP,
    RATE_LIMIT_WINDOW,
)
from rate_limiter import check_user_rate_limit, check_ip_rate_limit

app = FastAPI(title="SmartChatBot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class MessageRequest(BaseModel):
    conversation_id: int | None = None
    content: str
    image_data: str | None = None


class AuditQuery(BaseModel):
    limit: int = 50
    offset: int = 0


class SecurityCheckRequest(BaseModel):
    content: str


@app.post("/api/register")
def register(req: RegisterRequest, request: Request):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = %s", (req.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")
        hashed = hash_password(req.password)
        cur.execute(
            "INSERT INTO users (username, password_hash, role, email) VALUES (%s, %s, 'user', %s) RETURNING id",
            (req.username, hashed, req.email or ""),
        )
        user_id = cur.fetchone()[0]
        client_ip = request.client.host if request.client else "unknown"
        log_action(user_id, req.username, "REGISTER", "users", user_id, ip_address=client_ip)
    return {"message": "User registered"}


@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = %s",
            (req.username,),
        )
        row = cur.fetchone()
        if not row or not verify_password(req.password, row[2]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_access_token({"sub": row[1], "role": row[3]})
        client_ip = request.client.host if request.client else "unknown"
        log_action(row[0], row[1], "LOGIN", None, None, ip_address=client_ip)
    return {"access_token": token, "token_type": "bearer", "user_id": row[0], "username": row[1]}


@app.post("/api/security-check")
def security_check(
    req: SecurityCheckRequest,
    user: dict = Depends(get_current_user),
):
    sanitized, pii_types, risk_level = detect_and_redact(req.content)
    is_injection, injection_type, _ = detect_injection(req.content)
    return {
        "risk_level": risk_level,
        "pii_types": pii_types,
        "injection_detected": is_injection,
        "injection_type": injection_type,
        "sanitized_preview": sanitized,
    }


@app.post("/api/chat")
def chat(
    req: MessageRequest,
    user: dict = Depends(get_current_user),
    request: Request = None,
):
    raw_content = req.content
    client_ip = request.client.host if request and request.client else "unknown"

    # 1. 速率限制检查（先 IP，再用户）
    ip_ok, ip_remaining, ip_reset = check_ip_rate_limit(client_ip)
    if not ip_ok:
        raise HTTPException(status_code=429, detail=f"IP rate limit exceeded, retry after {ip_reset}s")
    user_ok, user_remaining, user_reset = check_user_rate_limit(str(user["id"]))
    if not user_ok:
        raise HTTPException(status_code=429, detail=f"User rate limit exceeded, retry after {user_reset}s")

    # 2. 注入检测
    if INJECTION_DETECTION_ENABLED:
        is_injection, injection_type, _ = detect_injection(raw_content)
        if is_injection:
            raise HTTPException(
                status_code=400,
                detail=f"Injection detected: {injection_type}",
            )

    # 3. PII 检测 + 风险定级
    sanitized_content, pii_types, risk_level = detect_and_redact(raw_content)

    # 4. 三级干预逻辑
    if risk_level == 3:
        processing_strategy = "blocked"
        with get_cursor() as cur:
            if req.conversation_id:
                conv_id = req.conversation_id
            else:
                cur.execute(
                    "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING id",
                    (user["id"], raw_content[:50]),
                )
                conv_id = cur.fetchone()[0]
            cur.execute(
                """INSERT INTO messages
                   (conversation_id, role, raw_content, sanitized_content, pii_redacted, pii_types_redacted, image_data, risk_level, processing_strategy)
                   VALUES (%s, 'user', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    conv_id,
                    raw_content,
                    sanitized_content,
                    bool(pii_types),
                    pii_types if pii_types else None,
                    req.image_data,
                    risk_level,
                    processing_strategy,
                ),
            )
            msg_id = cur.fetchone()[0]
        log_action(
            user["id"],
            user["username"],
            "CHAT_BLOCKED",
            "messages",
            msg_id,
            detail=f"Blocked high-risk PII: {pii_types}",
            ip_address=client_ip,
            risk_level=risk_level,
            processing_strategy=processing_strategy,
            pii_types_detected=pii_types,
        )
        return {
            "blocked": True,
            "reason": "High-risk PII detected",
            "risk_level": risk_level,
            "pii_types": pii_types,
            "sanitized_content": sanitized_content,
            "conversation_id": conv_id,
            "message_id": msg_id,
            "processing_strategy": processing_strategy,
        }

    if risk_level == 2:
        processing_strategy = "redacted"
        content_to_send = sanitized_content
    else:
        processing_strategy = "direct"
        content_to_send = raw_content

    if req.conversation_id:
        conv_id = req.conversation_id
    else:
        with get_cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (user_id, title) VALUES (%s, %s) RETURNING id",
                (user["id"], raw_content[:50]),
            )
            conv_id = cur.fetchone()[0]

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO messages
               (conversation_id, role, raw_content, sanitized_content, pii_redacted, pii_types_redacted, image_data, risk_level, processing_strategy)
               VALUES (%s, 'user', %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (
                conv_id,
                raw_content,
                sanitized_content,
                bool(pii_types),
                pii_types if pii_types else None,
                req.image_data,
                risk_level,
                processing_strategy,
            ),
        )
        msg_id = cur.fetchone()[0]

    log_action(
        user["id"],
        user["username"],
        "CHAT_MESSAGE",
        "messages",
        msg_id,
        detail=f"PII redacted: {bool(pii_types)}" if pii_types else "No PII detected",
        ip_address=client_ip,
        risk_level=risk_level,
        processing_strategy=processing_strategy,
        pii_types_detected=pii_types,
    )

    llm_reply = None
    if LLM_ENABLED:
        context = build_conversation_context(conv_id)
        if req.image_data:
            context.append({"role": "user", "content": "[User attached an image]"})
        llm_reply = chat_with_llm(context)

        if llm_reply:
            with get_cursor() as cur:
                cur.execute(
                    """INSERT INTO messages
                       (conversation_id, role, raw_content, sanitized_content)
                       VALUES (%s, 'assistant', %s, %s) RETURNING id""",
                    (conv_id, llm_reply, llm_reply),
                )
                reply_msg_id = cur.fetchone()[0]
            log_action(
                user["id"],
                user["username"],
                "LLM_REPLY",
                "messages",
                reply_msg_id,
                detail=f"LLM response generated (tokens: ~{len(llm_reply)//4})",
                ip_address=client_ip,
            )

    return {
        "conversation_id": conv_id,
        "message_id": msg_id,
        "sanitized_content": sanitized_content,
        "pii_redacted": bool(pii_types),
        "pii_types": pii_types,
        "llm_reply": llm_reply,
        "llm_enabled": LLM_ENABLED,
        "risk_level": risk_level,
        "processing_strategy": processing_strategy,
    }


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: dict = Depends(get_current_user), request: Request = None):
    with get_cursor() as cur:
        cur.execute("SELECT user_id FROM conversations WHERE id = %s", (conv_id,))
        conv = cur.fetchone()
        if not conv or conv[0] != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        cur.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
        cur.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))
    client_ip = request.client.host if request and request.client else "unknown"
    log_action(user["id"], user["username"], "DELETE_CONVERSATION", "conversations", conv_id, ip_address=client_ip)
    return {"message": "Conversation deleted"}


@app.get("/api/conversations")
def list_conversations(user: dict = Depends(get_current_user)):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, title, created_at FROM conversations WHERE user_id = %s ORDER BY created_at DESC",
            (user["id"],),
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "title": r[1], "created_at": r[2].isoformat()}
            for r in rows
        ]


@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: int, user: dict = Depends(get_current_user)):
    with get_cursor() as cur:
        cur.execute(
            "SELECT user_id FROM conversations WHERE id = %s",
            (conv_id,),
        )
        conv = cur.fetchone()
        if not conv or conv[0] != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        cur.execute(
            """SELECT id, role, raw_content, sanitized_content, pii_redacted, pii_types_redacted, image_data, created_at, risk_level, processing_strategy
               FROM messages WHERE conversation_id = %s ORDER BY created_at""",
            (conv_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "role": r[1],
                "raw_content": r[2], "sanitized_content": r[3],
                "pii_redacted": r[4], "pii_types_redacted": r[5],
                "image_data": r[6],
                "created_at": r[7].isoformat(),
                "risk_level": r[8],
                "processing_strategy": r[9],
            }
            for r in rows
        ]


@app.get("/api/audit-logs")
def get_audit_logs(limit: int = 50, offset: int = 0, user: dict = Depends(get_current_user)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, user_id, username, action_type, table_name, record_id, detail, ip_address, created_at, risk_level, pii_types_detected, processing_strategy
               FROM audit_log ORDER BY created_at DESC LIMIT %s OFFSET %s""",
            (limit, offset),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "user_id": r[1], "username": r[2],
                "action_type": r[3], "table_name": r[4], "record_id": r[5],
                "detail": r[6], "ip_address": r[7],
                "created_at": r[8].isoformat(),
                "risk_level": r[9],
                "pii_types_detected": r[10],
                "processing_strategy": r[11],
            }
            for r in rows
        ]


@app.get("/api/security-logs")
def get_security_logs(user: dict = Depends(get_current_user)):
    with get_cursor() as cur:
        cur.execute(
            """SELECT id, user_id, username, action_type, table_name, record_id, detail, ip_address, created_at, risk_level, pii_types_detected, processing_strategy
               FROM audit_log
               WHERE user_id = %s AND action_type IN ('CHAT_MESSAGE', 'CHAT_BLOCKED', 'SECURITY_CHECK')
               ORDER BY created_at DESC""",
            (user["id"],),
        )
        rows = cur.fetchall()
        return {
            "logs": [
                {
                    "id": r[0], "user_id": r[1], "username": r[2],
                    "action_type": r[3], "table_name": r[4], "record_id": r[5],
                    "detail": r[6], "ip_address": r[7],
                    "created_at": r[8].isoformat(),
                    "risk_level": r[9],
                    "pii_types_detected": r[10],
                    "processing_strategy": r[11],
                }
                for r in rows
            ]
        }


@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
