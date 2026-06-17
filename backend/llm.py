from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = (
    "You are a security-aware chatbot. "
    "The user's message has been scanned for PII (emails, phones, credit cards, etc.) "
    "and any detected PII has been replaced with placeholders like [EMAIL_REDACTED]. "
    "Do NOT ask the user to provide the redacted information. "
    "Be helpful and answer their questions naturally."
)

def get_active_config() -> dict | None:
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute(
                "SELECT api_key, base_url, model FROM api_configs WHERE is_active = true LIMIT 1"
            )
            row = cur.fetchone()
            if row and row[0]:
                return {"api_key": row[0], "base_url": row[1] or DEEPSEEK_BASE_URL, "model": row[2] or DEEPSEEK_MODEL}
    except Exception:
        pass
    return None

def is_llm_enabled() -> bool:
    config = get_active_config()
    if config and config["api_key"]:
        return True
    return bool(DEEPSEEK_API_KEY)

def chat_with_llm(messages: list[dict]) -> str | None:
    config = get_active_config()
    if not config or not config["api_key"]:
        if not DEEPSEEK_API_KEY:
            return None
        config = {"api_key": DEEPSEEK_API_KEY, "base_url": DEEPSEEK_BASE_URL, "model": DEEPSEEK_MODEL}

    try:
        client = OpenAI(api_key=config["api_key"], base_url=config["base_url"])
        formatted = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            formatted.append({"role": m["role"], "content": m["content"]})

        resp = client.chat.completions.create(
            model=config["model"],
            messages=formatted,
            temperature=0.7,
            max_tokens=2048,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"[LLM Error: {e}]"

def build_conversation_context(conv_id: int) -> list[dict]:
    from database import get_cursor
    with get_cursor() as cur:
        cur.execute(
            """SELECT role, COALESCE(sanitized_content, raw_content) AS content
               FROM messages
               WHERE conversation_id = %s AND role IN ('user', 'assistant') AND image_data IS NULL
               ORDER BY created_at
               LIMIT 20""",
            (conv_id,),
        )
        return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]

def get_current_model_info() -> dict:
    config = get_active_config()
    if config:
        return {"name": config["model"], "provider": config["base_url"].split("//")[-1].split(".")[0] if "//" in config["base_url"] else config["base_url"]}
    return {"name": DEEPSEEK_MODEL, "provider": "env"}