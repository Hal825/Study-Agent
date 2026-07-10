"""
SSE Event Bus —— Agent 过程事件推送到前端。

前端通过 GET /api/agent/stream/{session_id} 订阅，
后端通过 EventBus.publish() 推送事件。
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """SSE 事件类型。"""
    # Agent 生命周期
    AGENT_START = "agent_start"
    AGENT_FINISH = "agent_finish"
    AGENT_ERROR = "agent_error"

    # 节点状态
    NODE_START = "node_start"
    NODE_FINISH = "node_finish"

    # Tool 调用
    TOOL_START = "tool_start"
    TOOL_FINISH = "tool_finish"

    # 阶段进度
    STAGE_CHANGE = "stage_change"

    # Human-in-the-loop
    HUMAN_CONFIRM_REQUIRED = "human_confirm_required"

    # 结果流式输出
    STREAM_CHUNK = "stream_chunk"


@dataclass
class AgentEvent:
    """一条 Agent 事件。"""
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    session_id: str = ""


class EventBus:
    """
    SSE 事件总线。

    内部使用 asyncio.Queue 实现多消费者模式。
    每个 session 持有一个独立的消息 channel。
    """

    def __init__(self) -> None:
        # session_id -> list[asyncio.Queue]
        self._subscribers: dict[str, list[asyncio.Queue[AgentEvent]]] = {}

    def publish(self, event: AgentEvent) -> None:
        """发布事件到指定 session 的所有订阅者。"""
        queues = self._subscribers.get(event.session_id, [])
        if not queues:
            logger.debug(f"[EventBus] 无订阅者: session={event.session_id}, type={event.type}")
            return

        dead: list[int] = []
        for i, q in enumerate(queues):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(i)
                logger.warning(f"[EventBus] 队列已满, 丢弃事件: session={event.session_id}")

        # 清理已关闭的队列
        for i in reversed(dead):
            queues.pop(i)

    def subscribe(self, session_id: str) -> "SSESubscription":
        """创建一个 SSE 订阅。"""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue(maxsize=256)
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []
        self._subscribers[session_id].append(queue)
        return SSESubscription(queue=queue, bus=self, session_id=session_id)

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        """取消订阅。"""
        if session_id not in self._subscribers:
            return
        try:
            self._subscribers[session_id].remove(queue)
        except ValueError:
            pass
        if not self._subscribers[session_id]:
            del self._subscribers[session_id]


class SSESubscription:
    """一个 SSE 订阅的句柄。用作 async generator。"""

    def __init__(self, queue: asyncio.Queue[AgentEvent], bus: EventBus, session_id: str) -> None:
        self._queue = queue
        self._bus = bus
        self._session_id = session_id
        self._closed = False

    async def events(self) -> AsyncGenerator[str, None]:
        """
        SSE 事件生成器。

        用法（FastAPI StreamingResponse）:
            subscription = event_bus.subscribe(session_id)
            return StreamingResponse(
                subscription.events(),
                media_type="text/event-stream",
            )
        """
        try:
            while not self._closed:
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=30)
                    yield self._format_sse(event)
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.close()

    def close(self) -> None:
        """关闭订阅。"""
        if not self._closed:
            self._closed = True
            self._bus.unsubscribe(self._session_id, self._queue)

    @staticmethod
    def _format_sse(event: AgentEvent) -> str:
        """格式化为 SSE 协议字符串。"""
        data = json.dumps(
            {"type": event.type.value, "data": event.data},
            ensure_ascii=False,
        )
        return f"event: {event.type.value}\ndata: {data}\n\n"


# ============================================================
# 事件构造辅助函数
# ============================================================

def make_event(event_type: EventType, session_id: str, **data: Any) -> AgentEvent:
    """快捷构造 AgentEvent。"""
    return AgentEvent(type=event_type, data=data, session_id=session_id)


def stage_change(session_id: str, stage_index: int, stage_label: str) -> AgentEvent:
    """构造阶段变更事件。"""
    return make_event(
        EventType.STAGE_CHANGE, session_id,
        stage_index=stage_index, stage_label=stage_label,
    )


def tool_start(session_id: str, tool_name: str, tool_input: dict) -> AgentEvent:
    """构造 Tool 开始事件。"""
    return make_event(
        EventType.TOOL_START, session_id,
        tool_name=tool_name, input=tool_input,
    )


def tool_finish(session_id: str, tool_name: str, duration_ms: float) -> AgentEvent:
    """构造 Tool 完成事件。"""
    return make_event(
        EventType.TOOL_FINISH, session_id,
        tool_name=tool_name, duration_ms=duration_ms,
    )


def human_confirm_required(session_id: str, question: str, options: list[str]) -> AgentEvent:
    """构造「需要人类确认」事件。"""
    return make_event(
        EventType.HUMAN_CONFIRM_REQUIRED, session_id,
        question=question, options=options,
    )
