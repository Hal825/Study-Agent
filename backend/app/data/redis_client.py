"""
Redis 客户端模块 —— async Redis 单例管理。

用法:
    from app.data.redis_client import init_redis, get_redis_client, close_redis

    await init_redis("redis://localhost:6379/0")
    client = get_redis_client()
    await client.set("key", "value")
    await close_redis()
"""

import logging
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger("data.redis")

_redis_client: Optional[aioredis.Redis] = None


async def init_redis(redis_url: str = "redis://localhost:6379/0") -> None:
    """
    初始化 Redis 异步客户端。

    decode_responses=False 以支持 pickle 序列化二进制数据。
    """
    global _redis_client

    _redis_client = aioredis.from_url(
        redis_url,
        decode_responses=False,
        max_connections=20,
    )
    # 验证连接
    await _redis_client.ping()
    logger.info(f"Redis 已连接: {redis_url}")


def get_redis_client() -> aioredis.Redis:
    """
    获取 Redis 客户端实例。

    Raises:
        RuntimeError: 未调用 init_redis
    """
    if _redis_client is None:
        raise RuntimeError("Redis 未初始化，请先调用 init_redis()")
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接。"""
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis 已关闭")
