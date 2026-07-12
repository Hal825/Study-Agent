"""
AgentExecutor —— 运行 LangGraph 图并通过 EventBus 推送 SSE 事件。

连接 Agent 层与 API 层的桥梁。
"""

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Optional

from app.agent.state import NoteAgentState
from app.agent.graph import build_note_graph
from app.agent.nodes import inject_dependencies
from app.skills.note_gen import STAGE_LABELS
from app.skills.base import BaseSkill
from app.tools.interfaces import IToolRegistry
from app.services.llm_service import LLMService
from app.services.event_bus import (
    EventBus,
    EventType,
    make_event,
    stage_change,
    tool_start,
    tool_finish,
    human_confirm_required,
)
from app.data.interfaces import NoteRepository, StudyNote, UserPreferenceRepository

logger = logging.getLogger("agent.executor")


class AgentExecutor:
    """
    Agent 执行器。

    职责：
    1. 持有编译好的 LangGraph 图
    2. 注入 Tool Registry + LLM Service 到节点模块
    3. 运行图并将每个节点状态变更转为 SSE 事件
    4. 生成完成后自动持久化笔记到 NoteRepository
    """

    def __init__(
        self,
        tool_registry: IToolRegistry,
        llm_service: LLMService,
        event_bus: EventBus,
        skill: BaseSkill | None = None,
        note_repo: "NoteRepository | None" = None,
        user_pref_repo: "UserPreferenceRepository | None" = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._llm_service = llm_service
        self._event_bus = event_bus
        self._note_repo = note_repo
        self._user_pref_repo = user_pref_repo

        logger.info(
            "AgentExecutor 初始化: note_repo=%s, user_pref_repo=%s",
            type(note_repo).__name__ if note_repo else "None",
            type(user_pref_repo).__name__ if user_pref_repo else "None",
        )

        # Use skill's graph if provided, otherwise fall back to legacy build
        if skill is not None:
            self._skill = skill
            self._graph = skill.build_graph()
        else:
            self._skill = None
            self._graph = build_note_graph()
            # Legacy mode: inject tools into nodes module globals
            inject_dependencies(tool_registry=tool_registry, llm_service=llm_service)

    async def run_stream(
        self,
        content: str,
        template_id: str,
        session_id: str,
    ) -> AsyncIterator[str]:
        """
        运行 Agent 图并以 SSE 格式流式返回事件。

        若图在 confirm 节点前中断（interrupt_before），
        发送 human_confirm_required 事件后停止，
        等待前端调用 resume_stream() 恢复。

        Args:
            content: 用户上传的学习内容
            template_id: 笔记模板 ID
            session_id: 会话 ID（用于 EventBus 路由 + LangGraph thread_id）

        Yields:
            SSE 格式的事件字符串（可直接用于 StreamingResponse）
        """
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

            async for chunk in self._graph.astream(initial_state, config):
                for node_name, state_update in chunk.items():
                    # Skip LangGraph internal interrupt pseudo-node
                    if node_name == "__interrupt__":
                        continue

                    logger.info(f"[{session_id}] 节点完成: {node_name}")

                    label = STAGE_LABELS.get(node_name, node_name)
                    yield _sse(stage_change(session_id, stage_idx, label))

                    yield _sse(make_event(
                        EventType.NODE_FINISH, session_id,
                        node=node_name, stage_index=stage_idx,
                    ))

                    if isinstance(state_update, dict) and state_update.get("error"):
                        yield _sse(make_event(
                            EventType.AGENT_ERROR, session_id,
                            error=state_update["error"], node=node_name,
                        ))
                        return

                    stage_idx += 1

            # 3. 检查是否被中断（interrupt_before）
            graph_state = self._graph.get_state(config)
            if graph_state.next:
                # Graph has more nodes → interrupted before 'confirm'
                logger.info(f"[{session_id}] Graph interrupted, next: {graph_state.next}")
                yield _sse(human_confirm_required(
                    session_id,
                    question=f"确认使用模板「{template_id}」生成笔记？",
                    options=["outline", "summary", "cornell", "qa"],
                ))
                return  # 停止，等待前端调用 resume

            # 4. Graph 正常完成 → 持久化 + agent_finish
            final_state = graph_state
            generated_note = ""
            if final_state and final_state.values:
                generated_note = final_state.values.get("generated_note", "")

            await self._save_note(
                content=content,
                template_id=template_id,
                generated_note=generated_note,
                session_id=session_id,
            )

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

    async def resume_stream(
        self,
        session_id: str,
        confirmed_template: str | None = None,
    ) -> AsyncIterator[str]:
        """
        从中断点恢复 Agent 图执行。

        Called after user confirms template choice via
        POST /api/agent/note/confirm/{session_id}.

        Args:
            session_id: 与 run_stream() 中相同的 thread_id
            confirmed_template: 用户确认的模板 ID (None = 保持原选择)

        Yields:
            SSE 事件字符串 (confirm → generate → agent_finish)
        """
        config = {"configurable": {"thread_id": session_id}}

        try:
            # 写入确认状态
            update_values: dict[str, Any] = {"human_confirmed": True}
            if confirmed_template:
                update_values["template_id"] = confirmed_template
            self._graph.update_state(config, update_values)
            logger.info(f"[{session_id}] 恢复执行, template={confirmed_template}")

            # 记住用户偏好
            if confirmed_template and self._user_pref_repo:
                try:
                    await self._user_pref_repo.update(
                        "anonymous", {"preferred_template": confirmed_template}
                    )
                except Exception as e:
                    logger.debug(f"[{session_id}] 保存偏好失败(已忽略): {e}")

            # 从 checkpoint 继续 (confirm → generate)
            stage_idx = 3  # 0=parse, 1=extract, 2=analyze, 3=confirm, 4=generate

            async for chunk in self._graph.astream(None, config):
                for node_name, state_update in chunk.items():
                    logger.info(f"[{session_id}] 节点完成(恢复): {node_name}")

                    label = STAGE_LABELS.get(node_name, node_name)
                    yield _sse(stage_change(session_id, stage_idx, label))

                    yield _sse(make_event(
                        EventType.NODE_FINISH, session_id,
                        node=node_name, stage_index=stage_idx,
                    ))

                    if isinstance(state_update, dict) and state_update.get("error"):
                        yield _sse(make_event(
                            EventType.AGENT_ERROR, session_id,
                            error=state_update["error"], node=node_name,
                        ))
                        return

                    stage_idx += 1

            # 持久化 + 发送最终结果
            final_state = await self._graph.aget_state(config)
            generated_note = ""
            if final_state and final_state.values:
                generated_note = final_state.values.get("generated_note", "")

            await self._save_note(
                content=final_state.values.get("content", "") if final_state and final_state.values else "",
                template_id=confirmed_template or "",
                generated_note=generated_note,
                session_id=session_id,
            )

            yield _sse(make_event(
                EventType.AGENT_FINISH, session_id,
                result=generated_note,
            ))

        except Exception as e:
            logger.error(f"[{session_id}] 恢复执行异常: {e}", exc_info=True)
            yield _sse(make_event(
                EventType.AGENT_ERROR, session_id,
                error=str(e),
            ))

    async def run_sync(self, content: str, template_id: str, session_id: str) -> str:
        """
        同步执行 Agent 图，返回生成的笔记文本。

        用于兼容旧的 POST /api/agent/note 端点。
        自动通过 interrupt 点（不需要人类确认）。

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

        # 逐节点执行（到 interrupt 点为止）
        async for chunk in self._graph.astream(initial_state, config):
            for node_name, state_update in chunk.items():
                if isinstance(state_update, dict) and state_update.get("error"):
                    raise RuntimeError(f"Agent 节点 [{node_name}] 失败: {state_update['error']}")

        # 检查是否被中断 —— 如果是，自动确认并恢复
        graph_state = self._graph.get_state(config)
        if graph_state.next:
            logger.info(f"[{session_id}] 自动通过 interrupt, next: {graph_state.next}")
            self._graph.update_state(config, {"human_confirmed": True})

            async for chunk in self._graph.astream(None, config):
                for node_name, state_update in chunk.items():
                    if isinstance(state_update, dict) and state_update.get("error"):
                        raise RuntimeError(f"Agent 节点 [{node_name}] 失败: {state_update['error']}")

        # 持久化 + 返回最终结果
        final_state = await self._graph.aget_state(config)
        if final_state and final_state.values:
            result = final_state.values.get("generated_note", "")
            if result:
                await self._save_note(
                    content=content,
                    template_id=template_id,
                    generated_note=result,
                    session_id=session_id,
                )
                return result

        raise RuntimeError("Agent 执行完成但未生成笔记内容")

    # ----------------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------------

    async def _save_note(
        self,
        content: str,
        template_id: str,
        generated_note: str,
        session_id: str,
    ) -> None:
        """将生成的笔记持久化到 NoteRepository（静默失败，不影响主流程）。"""
        if self._note_repo is None:
            return
        try:
            title = generated_note.strip().split("\n")[0].lstrip("# ").strip()[:120]
            note = StudyNote(
                user_id="anonymous",
                title=title,
                template=template_id,
                content=generated_note,
                source_content=content[:5000],
                created_at=time.time(),
            )
            await self._note_repo.save(note)
            logger.info(f"[{session_id}] 笔记已保存: {note.id}")
        except Exception as e:
            logger.error(f"[{session_id}] 笔记保存失败(已忽略): {e}")


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
