import re

BUILTIN_PATTERNS = {
    "EMAIL_ADDRESS": r'(?<![A-Za-z0-9])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?![A-Za-z0-9])',
    "PHONE_NUMBER": r'(?<!\d)(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}(?!\d)',
    "CREDIT_CARD": r'(?<!\d)(?:\d{4}[-\s]?){3}\d{4}(?!\d)',
    "IP_ADDRESS": r'(?<!\d)\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!\d)',
    "URL": r'https?://[^\s]+',
    "SSN": r'(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)',
    "CHINA_ID_CARD": r'(?<!\d)\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)',
    "CHINA_PHONE": r'(?<!\d)1[3-9]\d{9}(?!\d)',
    "BANK_CARD": r'(?<!\d)(?:62|4[0-9]|5[1-5])\d{14,17}(?!\d)',
    "PASSPORT": r'(?<!\d)[Ee]\d{8}(?!\d)|(?<!\d)[Ss]\d{8}(?!\d)|(?<!\d)[Dd]\d{8}(?!\d)|(?<!\d)[Pp]\d{8}(?!\d)|(?<!\d)1[45]\d{7}(?!\d)',
    "MILITARY_ID": r'(?:南|北|沈|兰|济|广|成|海|空|参|政|后|装|武)\字第\d{6,8}号',
}

def get_custom_patterns() -> dict:
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT name, pattern FROM custom_pii")
            return {f"CUSTOM_{r[0]}": r[1] for r in cur.fetchall()}
    except Exception:
        return {}

def get_custom_risk_levels() -> dict[int, set]:
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT name, risk_level FROM custom_pii")
            result: dict[int, set] = {}
            for r in cur.fetchall():
                level = r[1]
                if level not in result:
                    result[level] = set()
                result[level].add(f"CUSTOM_{r[0]}")
            return result
    except Exception:
        return {}

def build_full_patterns() -> dict:
    patterns = dict(BUILTIN_PATTERNS)
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT name, pattern FROM custom_pii")
            for r in cur.fetchall():
                patterns[f"CUSTOM_{r[0]}"] = r[1]
    except Exception:
        pass
    return patterns

def build_full_risk_levels() -> dict[int, set]:
    levels = {
        1: {"EMAIL_ADDRESS", "URL", "IP_ADDRESS"},
        2: {"PHONE_NUMBER", "CHINA_PHONE", "CREDIT_CARD", "BANK_CARD"},
        3: {"CHINA_ID_CARD", "PASSPORT", "MILITARY_ID", "SSN"},
    }
    try:
        from database import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT name, risk_level FROM custom_pii")
            for r in cur.fetchall():
                level = r[1]
                if level not in levels:
                    levels[level] = set()
                levels[level].add(f"CUSTOM_{r[0]}")
    except Exception:
        pass
    return levels

def assess_risk_level(pii_types: list[str], risk_levels: dict[int, set | None] = None) -> int:
    if not pii_types:
        return 1
    if risk_levels is None:
        risk_levels = build_full_risk_levels()
    levels = set()
    for level, types in risk_levels.items():
        if types and any(t in types for t in pii_types):
            levels.add(level)
    return max(levels) if levels else 1

def detect_and_redact(text: str) -> tuple[str, list[str], int]:
    if not text or not text.strip():
        return text, [], 1

    patterns = build_full_patterns()
    risk_levels = build_full_risk_levels()
    found_types = set()
    result = text

    for entity_type, pattern in patterns.items():
        try:
            matches = list(re.finditer(pattern, result))
        except re.error:
            continue
        if matches:
            found_types.add(entity_type)
            for m in reversed(matches):
                placeholder = f"[{entity_type}_REDACTED]"
                result = result[:m.start()] + placeholder + result[m.end():]

    pii_types = sorted(found_types)
    risk_level = assess_risk_level(pii_types, risk_levels)
    return result, pii_types, risk_level