import time
from collections import defaultdict

# 内存存储: key -> list[timestamp]
_request_logs: dict[str, list[float]] = defaultdict(list)


def _cleanup_old_requests(timestamps: list[float], window_seconds: int, now: float) -> list[float]:
    """清理超出时间窗口的旧请求记录。"""
    cutoff = now - window_seconds
    return [ts for ts in timestamps if ts > cutoff]


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
    """基于内存字典的简单速率限制检查。

    参数:
        key: 限流标识（如 user_id 或 ip）
        max_requests: 时间窗口内允许的最大请求数
        window_seconds: 时间窗口长度（秒）

    返回:
        allowed: 是否允许本次请求
        remaining: 剩余可用请求数
        reset_after: 窗口重置还需多少秒
    """
    now = time.time()
    timestamps = _request_logs.get(key, [])
    timestamps = _cleanup_old_requests(timestamps, window_seconds, now)

    if len(timestamps) >= max_requests:
        # 计算窗口重置时间
        oldest = min(timestamps)
        reset_after = int((oldest + window_seconds) - now) + 1
        reset_after = max(reset_after, 1)
        _request_logs[key] = timestamps
        return False, 0, reset_after

    timestamps.append(now)
    _request_logs[key] = timestamps
    remaining = max_requests - len(timestamps)
    reset_after = window_seconds
    return True, remaining, reset_after


def check_user_rate_limit(user_id: str) -> tuple[bool, int, int]:
    """检查用户级别速率限制：60 请求 / 分钟。"""
    return check_rate_limit(f"user:{user_id}", max_requests=60, window_seconds=60)


def check_ip_rate_limit(ip: str) -> tuple[bool, int, int]:
    """检查 IP 级别速率限制：100 请求 / 分钟。"""
    return check_rate_limit(f"ip:{ip}", max_requests=100, window_seconds=60)
