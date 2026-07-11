"""
AgentExecutor —— 运行 LangGraph 图并通过 EventBus 推送 SSE 事件。

连接 Agent 层与 API 层的桥梁。
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Optional

from app.agent.state import NoteAgentState
from app.agent.graph import build_note_graph
from app.agent.nodes import inject_dependencies, STAGE_LABELS
from app.tools.interfaces import IToolRegistry
from app.services.llm_service import LLMService
from app.services.event_bus import (
    EventBus,
    EventType,
    make_event,
    stage_change,
    tool_start,
    tool_finish,
)

logger = logging.getLogger("agent.executor")


class AgentExecutor:
    """
    Agent 执行器。

    职责：
    1. 持有编译好的 LangGraph 图
    2. 注入 Tool Registry + LLM Service 到节点模块
    3. 运行图并将每个节点状态变更转为 SSE 事件
    """

    def __init__(
        self,
        tool_registry: IToolRegistry,
        llm_service: LLMService,
        event_bus: EventBus,
    ) -> None:
        self._tool_registry = tool_registry
        self._llm_service = llm_service
        self._event_bus = event_bus
        self._graph = build_note_graph()

        # 依赖注入到节点模块（模块级变量）
        inject_dependencies(tool_registry=tool_registry, llm_service=llm_service)

    async def run_stream(
        self,
        content: str,
        template_id: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        运行 Agent 图并以 SSE 格式流式返回事件。

        Args:
            content: 用户上传的学习内容
            template_id: 笔记模板 ID
            session_id: 会话 ID（用于 EventBus 路由）

        Yields:
            SSE 格式的事件字符串（可直接用于 StreamingResponse）
        """
        # 初始状态
        initial_state: NoteAgentState = {
            "content": content,
            "template_id": template_id,
            "session_id": session_id,
            "stage": "start",
        }

        config = {"configurable": {"thread_id": session_id}}

        try:
            # 1. 发送 agent_start 事件
            yield _sse(make_event(
                EventType.AGENT_START, session_id,
                template=template_id, content_length=len(content),
            ))

            # 2. 逐节点执行图
            stage_idx = 0
            node_names = ["parse", "extract", "analyze", "confirm", "generate"]

            async for chunk in self._graph.astream(initial_state, config):
                # chunk 结构: {node_name: state_update_dict}
                for node_name, state_update in chunk.items():
                    logger.info(f"[{session_id}] 节点完成: {node_name}")

                    # 阶段变更事件
                    label = STAGE_LABELS.get(node_name, node_name)
                    yield _sse(stage_change(session_id, stage_idx, label))

                    # 节点完成事件
                    yield _sse(make_event(
                        EventType.NODE_FINISH, session_id,
                        node=node_name, stage_index=stage_idx,
                    ))

                    # 检查是否有错误
                    if isinstance(state_update, dict) and state_update.get("error"):
                        yield _sse(make_event(
                            EventType.AGENT_ERROR, session_id,
                            error=state_update["error"], node=node_name,
                        ))
                        return

                    stage_idx += 1

            # 3. 发送 agent_finish 事件（包含生成的笔记）
            final_state = await self._graph.aget_state(config)
            generated_note = ""
            if final_state and final_state.values:
                generated_note = final_state.values.get("generated_note", "")

            yield _sse(make_event(
                EventType.AGENT_FINISH, session_id,
                result=generated_note,
            ))

        except Exception as e:
            logger.error(f"[{session_id}] Agent 执行异常: {e}", exc_info=True)
            yield _sse(make_event(
                EventType.AGENT_ERROR, session_id,
                error=str(e),
            ))

    async def run_sync(self, content: str, template_id: str, session_id: str) -> str:
        """
        同步执行 Agent 图，返回生成的笔记文本。

        用于兼容旧的 POST /api/agent/note 端点。

        Returns:
            生成的 Markdown 笔记文本

        Raises:
            RuntimeError: Agent 执行失败
        """
        initial_state: NoteAgentState = {
            "content": content,
            "template_id": template_id,
            "session_id": session_id,
            "stage": "start",
        }

        config = {"configurable": {"thread_id": session_id}}

        # 逐节点执行
        async for chunk in self._graph.astream(initial_state, config):
            for node_name, state_update in chunk.items():
                if isinstance(state_update, dict) and state_update.get("error"):
                    raise RuntimeError(f"Agent 节点 [{node_name}] 失败: {state_update['error']}")

        # 获取最终结果
        final_state = await self._graph.aget_state(config)
        if final_state and final_state.values:
            result = final_state.values.get("generated_note", "")
            if result:
                return result

        raise RuntimeError("Agent 执行完成但未生成笔记内容")


# ============================================================
# SSE 格式化辅助
# ============================================================

def _sse(event) -> str:
    """将一个 AgentEvent 格式化为 SSE 协议字符串。"""
    import json
    data = json.dumps(
        {"type": event.type.value, "data": event.data},
        ensure_ascii=False,
    )
    return f"event: {event.type.value}\ndata: {data}\n\n"
