"""
Redis cache decorator for admin GET endpoints.
Cache key: {key_prefix}:{company_id_or_all}:{sha256_of_query_params[:16]}
Falls through to the handler if Redis is unavailable.
"""
import hashlib
import json
import functools
import logging
from typing import Any, Callable

import redis.asyncio as aioredis
from backend.config import settings

logger = logging.getLogger("admin.cache")

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def cache_response(ttl: int, key_prefix: str) -> Callable:
    """
    Decorator for async FastAPI endpoint functions.
    Requires `ctx: TenantContext` to be a kwarg of the decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            ctx = kwargs.get("ctx")
            scope = str(ctx.company_id) if (ctx and ctx.is_company) else "all"

            param_str = json.dumps(
                {k: str(v) for k, v in kwargs.items() if k not in ("ctx", "db")},
                sort_keys=True,
            )
            param_hash = hashlib.sha256(param_str.encode()).hexdigest()[:16]
            cache_key = f"{key_prefix}:{scope}:{param_hash}"

            r = _get_redis()
            try:
                cached = await r.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("Redis GET failed: %s", exc)

            result = await func(*args, **kwargs)

            try:
                await r.set(cache_key, json.dumps(result, default=str), ex=ttl)
            except Exception as exc:
                logger.warning("Redis SET failed: %s", exc)

            return result
        return wrapper
    return decorator


async def invalidate_admin_cache(company_id: str | None = None) -> None:
    """Call after scan writes or consent changes to bust stale cache entries."""
    r = _get_redis()
    scope = str(company_id) if company_id else "*"
    patterns = [
        f"admin:overview:{scope}:*",
        f"admin:trends:{scope}:*",
        f"admin:heatmap:{scope}:*",
        f"admin:markets:{scope}:*",
        f"admin:states:{scope}:*",
    ]
    for pattern in patterns:
        try:
            keys = await r.keys(pattern)
            if keys:
                await r.delete(*keys)
        except Exception as exc:
            logger.warning("Redis invalidate failed for %s: %s", pattern, exc)
