from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, LLM_ENABLED

client = None
if LLM_ENABLED:
    from openai import OpenAI
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )

SYSTEM_PROMPT = (
    "You are a security-aware chatbot. "
    "The user's message has been scanned for PII (emails, phones, credit cards, etc.) "
    "and any detected PII has been replaced with placeholders like [EMAIL_REDACTED]. "
    "Do NOT ask the user to provide the redacted information. "
    "Be helpful and answer their questions naturally."
)

def chat_with_llm(messages: list[dict]) -> str | None:
    if not LLM_ENABLED or client is None:
        return None

    try:
        formatted = [{"role": "system", "content": SYSTEM_PROMPT}]
        for m in messages:
            formatted.append({"role": m["role"], "content": m["content"]})

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
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
