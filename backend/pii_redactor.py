import re

PII_PATTERNS = {
    "EMAIL_ADDRESS": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    "PHONE_NUMBER": r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',
    "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "IP_ADDRESS": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    "URL": r'https?://[^\s]+',
    "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
}

def detect_and_redact(text: str) -> tuple[str, list[str], bool]:
    if not text or not text.strip():
        return text, [], False

    found_types = set()
    result = text

    for entity_type, pattern in PII_PATTERNS.items():
        matches = list(re.finditer(pattern, result))
        if matches:
            found_types.add(entity_type)
            for m in reversed(matches):
                placeholder = f"[{entity_type}_REDACTED]"
                result = result[:m.start()] + placeholder + result[m.end():]

    return result, sorted(found_types), bool(found_types)
