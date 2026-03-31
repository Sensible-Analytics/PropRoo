import json
import hashlib
import redis as redis_lib
import logging
from functools import wraps
from app.config import settings

logger = logging.getLogger(__name__)
_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        if settings.redis_url:
            try:
                _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
                _redis.ping()
            except Exception:
                logger.warning("Failed to connect to Redis", exc_info=True)
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
                    logger.debug("Failed to get cached value", exc_info=True)
            result = await func(*args, **kwargs)
            if redis_client:
                try:
                    redis_client.setex(key, ttl, json.dumps(result, default=str))
                except Exception:
                    logger.debug("Failed to set cache value", exc_info=True)
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
            logger.warning("Failed to invalidate cache", exc_info=True)
