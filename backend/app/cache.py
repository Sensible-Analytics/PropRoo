import json
import hashlib
import redis as redis_lib
from functools import wraps
from app.config import settings

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        if settings.redis_url:
            try:
                _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
                _redis.ping()
            except Exception:
                _redis = None
    return _redis


DEFAULT_TTL = 300


def cache_key(*args, **kwargs) -> str:
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def cached(ttl: int = DEFAULT_TTL):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            redis_client = _get_redis()
            key = f"proproo:{func.__name__}:{cache_key(*args, **kwargs)}"
            if redis_client:
                try:
                    cached_val = redis_client.get(key)
                    if cached_val:
                        return json.loads(cached_val)
                except Exception:
                    pass
            result = await func(*args, **kwargs)
            if redis_client:
                try:
                    redis_client.setex(key, ttl, json.dumps(result, default=str))
                except Exception:
                    pass
            return result

        return wrapper

    return decorator


def invalidate_all():
    redis_client = _get_redis()
    if redis_client:
        try:
            keys = redis_client.keys("proproo:*")
            if keys:
                redis_client.delete(*keys)
        except Exception:
            pass
