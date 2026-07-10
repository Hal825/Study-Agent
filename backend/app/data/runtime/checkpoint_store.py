"""
Checkpoint 存储 —— 开发环境用内存实现。

线程安全，由 BaseMemoryStore 提供异步锁和统一日志。
"""

from typing import Optional
from collections import defaultdict

from app.data.runtime.base import BaseMemoryStore
from app.data.interfaces import CheckpointStore, CheckpointEntry


class MemoryCheckpointStore(BaseMemoryStore, CheckpointStore):
    """基于内存字典的 checkpoint 存储（线程安全）。"""

    def __init__(self) -> None:
        super().__init__(name="MemoryCheckpointStore")
        self._store: dict[str, dict[str, list[CheckpointEntry]]] = defaultdict(
            lambda: defaultdict(list)
        )

    # ---- CheckpointStore 接口实现 ----

    async def put(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: Optional[str],
        channel_values: dict,
        metadata: dict,
    ) -> None:
        async with self._locked_context("put", f"{thread_id}/{checkpoint_ns}/{checkpoint_id}"):
            entry = CheckpointEntry(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_checkpoint_id,
                channel_values=channel_values,
                metadata=metadata,
            )
            entries = self._store[thread_id][checkpoint_ns]
            for i, existing in enumerate(entries):
                if existing.checkpoint_id == checkpoint_id:
                    entries[i] = entry
                    return
            entries.append(entry)

    async def get(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> Optional[CheckpointEntry]:
        async with self._locked_context("get", f"{thread_id}/{checkpoint_ns}"):
            entries = self._store.get(thread_id, {}).get(checkpoint_ns, [])
            return entries[-1] if entries else None

    async def get_by_id(
        self, thread_id: str, checkpoint_id: str
    ) -> Optional[CheckpointEntry]:
        async with self._locked_context("get_by_id", f"{thread_id}/{checkpoint_id}"):
            for ns_entries in self._store.get(thread_id, {}).values():
                for entry in reversed(ns_entries):
                    if entry.checkpoint_id == checkpoint_id:
                        return entry
            return None

    async def list_checkpoints(
        self, thread_id: str, checkpoint_ns: str = ""
    ) -> list[CheckpointEntry]:
        async with self._locked_context("list", f"{thread_id}/{checkpoint_ns}"):
            return list(self._store.get(thread_id, {}).get(checkpoint_ns, []))

    async def delete_thread(self, thread_id: str) -> None:
        async with self._locked_context("delete_thread", thread_id):
            self._store.pop(thread_id, None)
