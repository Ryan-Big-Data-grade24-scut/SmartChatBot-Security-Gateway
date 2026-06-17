import os

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "smart_chatbot")
DB_USER = os.getenv("DB_USER", "chat_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ChatAdmin@2024")

SECRET_KEY = os.getenv("SECRET_KEY", "smart-chatbot-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

LLM_ENABLED = bool(DEEPSEEK_API_KEY)

RATE_LIMIT_PER_USER = int(os.getenv("RATE_LIMIT_PER_USER", "60"))
RATE_LIMIT_PER_IP = int(os.getenv("RATE_LIMIT_PER_IP", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
INJECTION_DETECTION_ENABLED = os.getenv("INJECTION_DETECTION_ENABLED", "true").lower() == "true"
