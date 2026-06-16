from database import get_cursor


def log_action(
    user_id: int | None,
    username: str | None,
    action_type: str,
    table_name: str | None = None,
    record_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    risk_level: int | None = None,
    processing_strategy: str | None = None,
    pii_types_detected: list[str] | None = None,
):
    extra_parts = []
    if risk_level is not None:
        extra_parts.append(f"risk_level={risk_level}")
    if processing_strategy is not None:
        extra_parts.append(f"processing_strategy={processing_strategy}")
    if pii_types_detected is not None:
        extra_parts.append(f"pii_types={','.join(pii_types_detected)}")
    if extra_parts:
        extra = "; ".join(extra_parts)
        detail = f"{detail}; {extra}" if detail else extra

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log
               (user_id, username, action_type, table_name, record_id, detail, ip_address, risk_level, pii_types_detected, processing_strategy)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, username, action_type, table_name, record_id, detail, ip_address, risk_level, pii_types_detected, processing_strategy),
        )
