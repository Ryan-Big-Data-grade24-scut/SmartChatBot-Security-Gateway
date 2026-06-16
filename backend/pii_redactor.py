import re

PII_PATTERNS = {
    "EMAIL_ADDRESS": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
    "PHONE_NUMBER": r'\b(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b',
    "CREDIT_CARD": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "IP_ADDRESS": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
    "URL": r'https?://[^\s]+',
    "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
    # 中国 PII
    "CHINA_ID_CARD": r'\b\d{6}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b',
    "CHINA_PHONE": r'\b1[3-9]\d{9}\b',
    "BANK_CARD": r'\b(?:62|4[0-9]|5[1-5])\d{14,17}\b',
    "PASSPORT": r'\b[Ee]\d{8}\b|\b[Ss]\d{8}\b|\b[Dd]\d{8}\b|\b[Pp]\d{8}\b|\b1[45]\d{7}\b',
    "MILITARY_ID": r'\b(?:南|北|沈|兰|济|广|成|海|空|参|政|后|装|武)\字第\d{6,8}号\b',
}

# 风险定级映射
RISK_LEVELS = {
    1: {"EMAIL_ADDRESS", "URL", "IP_ADDRESS"},
    2: {"PHONE_NUMBER", "CHINA_PHONE", "CREDIT_CARD", "BANK_CARD"},
    3: {"CHINA_ID_CARD", "PASSPORT", "MILITARY_ID", "SSN"},
}


def assess_risk_level(pii_types: list[str]) -> int:
    """根据检测到的 PII 类型评估风险等级。

    - 一级（低风险）：EMAIL_ADDRESS, URL, IP_ADDRESS → 直接发送
    - 二级（中风险）：PHONE_NUMBER, CHINA_PHONE, CREDIT_CARD, BANK_CARD → 脱敏后发送
    - 三级（高风险）：CHINA_ID_CARD, PASSPORT, MILITARY_ID, SSN → 拦截提示用户
    """
    if not pii_types:
        return 1

    levels = set()
    for level, types in RISK_LEVELS.items():
        if any(t in types for t in pii_types):
            levels.add(level)

    return max(levels) if levels else 1


def detect_and_redact(text: str) -> tuple[str, list[str], int]:
    """检测并脱敏文本中的 PII。

    返回:
        sanitized_content: 脱敏后的文本
        pii_types: 检测到的 PII 类型列表（已排序）
        risk_level: 风险等级（1/2/3）
    """
    if not text or not text.strip():
        return text, [], 1

    found_types = set()
    result = text

    for entity_type, pattern in PII_PATTERNS.items():
        matches = list(re.finditer(pattern, result))
        if matches:
            found_types.add(entity_type)
            for m in reversed(matches):
                placeholder = f"[{entity_type}_REDACTED]"
                result = result[:m.start()] + placeholder + result[m.end():]

    pii_types = sorted(found_types)
    risk_level = assess_risk_level(pii_types)
    return result, pii_types, risk_level
