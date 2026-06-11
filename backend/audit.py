from database import get_cursor

def log_action(
    user_id: int | None,
    username: str | None,
    action_type: str,
    table_name: str | None = None,
    record_id: int | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
):
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log
               (user_id, username, action_type, table_name, record_id, detail, ip_address)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, username, action_type, table_name, record_id, detail, ip_address),
        )
