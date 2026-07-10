"""
后台清理调度器 —— 定期清理 Runtime 存储中的过期数据。

解决惰性清理导致过期数据永久驻留的问题。
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("data.cleanup")


class CleanupScheduler:
    """
    后台清理调度器。

    管理一个周期性清理协程，调用已注册存储的 cleanup() 方法。
    """

    def __init__(self, interval_seconds: int = 300) -> None:
        """
        Args:
            interval_seconds: 清理间隔，默认 5 分钟
        """
        self._interval = interval_seconds
        self._stores: list["BaseMemoryStore"] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def register(self, store: "BaseMemoryStore") -> None:
        """注册一个需要定期清理的存储实例。"""
        if store not in self._stores:
            self._stores.append(store)
            logger.debug(f"注册清理目标: {store.store_name}")

    def unregister(self, store: "BaseMemoryStore") -> None:
        """取消注册。"""
        try:
            self._stores.remove(store)
            logger.debug(f"取消注册: {store.store_name}")
        except ValueError:
            pass

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动后台清理循环。幂等：重复调用无副作用。"""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._loop(), name="cleanup-scheduler")
        logger.info(
            f"清理调度器已启动, 间隔={self._interval}s, "
            f"目标={[s.store_name for s in self._stores]}"
        )

    async def stop(self) -> None:
        """停止后台清理。幂等。"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("清理调度器已停止")

    async def _loop(self) -> None:
        """
        主循环：每 self._interval 秒遍历所有注册存储并执行清理。

        使用 asyncio.sleep（而非 time.sleep）避免阻塞事件循环。
        异常隔离：单个 store 清理失败不影响其他 store。
        """
        while self._running:
            await asyncio.sleep(self._interval)
            if not self._running:
                break

            for store in self._stores:
                try:
                    count = await store.cleanup()
                    if count > 0:
                        logger.info(f"[{store.store_name}] 清理了 {count} 条过期数据")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error(
                        f"[{store.store_name}] 清理异常: {e}", exc_info=True
                    )

    async def run_once(self) -> dict[str, int]:
        """
        手动触发一次全量清理（调试/测试用）。

        Returns:
            {store_name: count} 每个 store 清理的数量。
        """
        result: dict[str, int] = {}
        for store in self._stores:
            try:
                count = await store.cleanup()
                result[store.store_name] = count
            except Exception as e:
                logger.error(f"[{store.store_name}] 手动清理失败: {e}")
                result[store.store_name] = -1
        return result
