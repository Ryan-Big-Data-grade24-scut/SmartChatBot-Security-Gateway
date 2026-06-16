import re

# 提示注入检测规则（不区分大小写）
INJECTION_RULES: list[tuple[str, str]] = [
    # 指令覆盖类
    ("instruction_override", r"ignore\s+(?:previous\s+instructions?|the\s+above|everything)"),
    ("instruction_override", r"forget\s+everything"),
    # 系统提示操控类
    ("system_prompt_manipulation", r"system\s+prompt"),
    ("system_prompt_manipulation", r"you\s+are\s+now"),
    ("system_prompt_manipulation", r"\bDAN\b"),
    ("system_prompt_manipulation", r"jailbreak"),
    ("system_prompt_manipulation", r"do\s+anything\s+now"),
    # 安全绕过类
    ("safety_bypass", r"override"),
    ("safety_bypass", r"bypass"),
    ("safety_bypass", r"disable\s+safety"),
    ("safety_bypass", r"ignore\s+rules?"),
    # 角色扮演类
    ("roleplay_request", r"pretend\s+to\s+be"),
    ("roleplay_request", r"act\s+as"),
    ("roleplay_request", r"roleplay\s+(?:as)?"),
]


def detect_injection(text: str) -> tuple[bool, str | None, float]:
    """检测文本中是否包含提示注入攻击。

    返回:
        is_injection: 是否检测到注入
        injection_type: 注入类型（如未检测到则为 None）
        confidence: 置信度（固定 0.9）
    """
    if not text or not text.strip():
        return False, None, 0.0

    lower_text = text.lower()

    for injection_type, pattern in INJECTION_RULES:
        if re.search(pattern, lower_text):
            return True, injection_type, 0.9

    return False, None, 0.0
