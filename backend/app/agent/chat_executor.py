"""
ChatAgentExecutor —— 运行对话式笔记生成的 LangGraph 图并通过 SSE 推送事件。

与 AgentExecutor（旧版表单式流程）不同，ChatAgentExecutor：
1. 支持多轮对话（run_stream → resume_stream → ...）
2. 在中断点注入设计框架 / 选项卡片等富文本事件
3. 支持 generate_note 阶段的流式输出（实时预览）
4. 支持修订循环（用户请求修改 → 重新生成）

SSE 事件流：
- run_stream: analyze → [design_framework + option_cards] → 中断
- resume_stream (confirm): [stream_chunks...] → note_result → 中断
- resume_stream (revision): [stream_chunks...] → note_result → 中断
- resume_stream (accept): chat_done
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

from app.agent.chat_state import ChatAgentState
from app.agent.chat_graph import build_chat_graph, inject_chat_dependencies
from app.services.event_bus import (
    EventBus,
    EventType,
    make_event,
    stage_change,
    chat_message_event,
    chat_design_framework_event,
    chat_option_cards_event,
    chat_stream_chunk_event,
    chat_note_result_event,
    chat_done_event,
)
from app.services.llm_service import LLMService, LLMRequest
from app.tools.interfaces import IToolRegistry
from app.prompts.registry import PromptRegistry
from app.data.interfaces import NoteRepository, StudyNote

logger = logging.getLogger("agent.chat_executor")


class ChatAgentExecutor:
    """
    对话式笔记生成执行器。

    职责：
    1. 持有编译好的对话式 LangGraph 图
    2. 注入 Tool Registry + LLM Service + Prompt Registry
    3. 运行图并将每个节点状态变更转为 SSE 事件
    4. 在中断点注入设计框架 / 选项卡片等富文本事件
    5. 在 generate_note 阶段提供流式 LLM 输出
    6. 支持多轮修订循环
    """

    def __init__(
        self,
        tool_registry: IToolRegistry,
        llm_service: LLMService,
        event_bus: EventBus,
        prompt_registry: PromptRegistry | None = None,
        note_repo: "NoteRepository | None" = None,
    ) -> None:
        self._tool_registry = tool_registry
        self._llm_service = llm_service
        self._event_bus = event_bus
        self._prompt_registry = prompt_registry
        self._note_repo = note_repo

        # 注入依赖到 chat_graph 模块
        inject_chat_dependencies(
            tool_registry=tool_registry,
            llm_service=llm_service,
            prompt_registry=prompt_registry,
        )

        # 构建图
        self._graph = build_chat_graph()

        logger.info(
            "ChatAgentExecutor 初始化: note_repo=%s",
            type(note_repo).__name__ if note_repo else "None",
        )

    # ================================================================
    # 公开方法
    # ================================================================

    async def run_stream(
        self,
        content: str,
        session_id: str | None = None,
    ) -> AsyncIterator[str]:
        """
        开始一个新的对话式笔记生成会话。

        流程：
        1. 创建 session + 初始状态
        2. 执行 analyze 节点（parse + extract + analyze）
        3. 执行到 present_design 节点前中断
        4. 发送设计框架 + 选项卡片事件
        5. 停止流，等待用户响应

        Args:
            content: 用户上传的学习内容
            session_id: 会话 ID（可选，不提供则自动生成）

        Yields:
            SSE 格式的事件字符串
        """
        session_id = session_id or f"chat_{uuid.uuid4().hex[:8]}"

        initial_state: ChatAgentState = {
            "session_id": session_id,
            "content": content,
            "phase": "init",
            "messages": [],
            "key_concepts": [],
            "main_topics": [],
            "suggested_outline": [],
            "parsed_sections": [],
            "parsed_title": "",
            "parsed_total_words": 0,
            "parsed_language": "zh",
            "content_type": "unknown",
            "complexity": "medium",
            "estimated_study_time_minutes": 30,
            "selected_template": "outline",
            "selected_topics": [],
            "enable_annotations": False,
            "enable_color_emphasis": False,
            "format_modifications": "",
            "custom_instructions": "",
            "generated_note": "",
            "revision_request": "",
            "revision_count": 0,
            "error": "",
            "human_confirmed": False,
        }

        config = {"configurable": {"thread_id": session_id}}

        try:
            # 2. 执行图到第一个中断点（present_design 之前）
            async for chunk in self._graph.astream(initial_state, config):
                for node_name, state_update in chunk.items():
                    if node_name == "__interrupt__":
                        continue

                    logger.info(f"[{session_id}] 节点完成: {node_name}")

                    if isinstance(state_update, dict) and state_update.get("error"):
                        yield _sse(make_event(
                            EventType.AGENT_ERROR, session_id,
                            error=state_update["error"],
                        ))
                        return

            # 3. 检查图是否中断
            graph_state = self._graph.get_state(config)
            if graph_state.next:
                logger.info(f"[{session_id}] 图中断于 present_design 之前，next={graph_state.next}")

                # 读取分析结果
                state_values = graph_state.values or {}
                # 获取 _design_framework_cache
                df_cache = state_values.get("_design_framework_cache", {})
                if not df_cache:
                    # 如果缓存中没有（可能 present_design 还没执行），
                    # 需要先执行一次 present_design_node
                    logger.info(f"[{session_id}] 设计框架缓存为空，手动构建")
                    df_cache = _build_design_framework_fallback(state_values)

                # 4. 发送设计框架事件
                yield _sse(chat_design_framework_event(session_id, df_cache))

                # 5. 发送 AI 消息
                yield _sse(chat_message_event(
                    session_id,
                    role="assistant",
                    message_type="text",
                    content=_build_design_message(state_values, df_cache),
                ))

                # 6. 发送选项卡片
                yield _sse(chat_option_cards_event(
                    session_id,
                    question="请选择你喜欢的笔记格式：",
                    options=[
                        {"id": "outline", "label": "大纲笔记", "description": "层次分明的结构化笔记，适合梳理知识体系", "emoji": "🌳"},
                        {"id": "summary", "label": "详细摘要", "description": "连贯的段落式总结，适合深入理解内容", "emoji": "📄"},
                        {"id": "cornell", "label": "康奈尔笔记", "description": "分区式笔记法：线索栏 + 笔记栏 + 总结栏", "emoji": "📋"},
                        {"id": "qa", "label": "问答笔记", "description": "以问答形式组织知识，适合备考和自测", "emoji": "💬"},
                    ],
                    multi_select=False,
                ))

                # 7. 发送确认提示
                yield _sse(chat_message_event(
                    session_id,
                    role="assistant",
                    message_type="text",
                    content="你还可以告诉我：你想重点关注哪些主题？是否需要添加学习批注？是否使用颜色强调？或者有其他格式偏好吗？",
                ))

            else:
                # 图已完成（不应发生，因为有中断）
                logger.warning(f"[{session_id}] 图意外完成，无中断")
                yield _sse(chat_done_event(session_id))

        except Exception as e:
            logger.error(f"[{session_id}] ChatAgent 执行异常: {e}", exc_info=True)
            yield _sse(make_event(
                EventType.AGENT_ERROR, session_id,
                error=str(e),
            ))

    async def resume_stream(
        self,
        session_id: str,
        user_message: str = "",
        selections: dict | None = None,
    ) -> AsyncIterator[str]:
        """
        从中断点恢复图执行。

        流程：
        1. 读取图状态，确定当前中断位置
        2. 根据用户消息/选项更新 state
        3. 如果下一个节点是 generate_note → 流式生成
        4. 如果下一个节点是 present_result → 展示结果
        5. 如果是修订 → 循环回 generate_note

        Args:
            session_id: 会话 ID
            user_message: 用户的自由文本回复
            selections: 用户的结构化选择（模板/选项等）

        Yields:
            SSE 事件字符串
        """
        config = {"configurable": {"thread_id": session_id}}
        selections = selections or {}

        try:
            # 1. 读取当前图状态
            graph_state = self._graph.get_state(config)
            if not graph_state:
                yield _sse(make_event(
                    EventType.AGENT_ERROR, session_id,
                    error=f"会话 {session_id} 不存在",
                ))
                return

            next_nodes = graph_state.next or []
            state_values = graph_state.values or {}
            logger.info(f"[{session_id}] resume: next={next_nodes}, phase={state_values.get('phase', '?')}")

            # 2. 解析用户意图 → 更新 state
            update: dict[str, Any] = {"human_confirmed": True}

            # 应用结构化选择
            if selections.get("template"):
                update["selected_template"] = selections["template"]
            if "annotations" in selections:
                update["enable_annotations"] = selections["annotations"]
            if "color_emphasis" in selections:
                update["enable_color_emphasis"] = selections["color_emphasis"]
            if selections.get("format_modifications"):
                update["format_modifications"] = selections["format_modifications"]
            if selections.get("topics"):
                update["selected_topics"] = selections["topics"]

            # 解析用户自由文本消息中的 intent
            phase = state_values.get("phase", "")
            if phase == "design":
                # 用户可能在消息中表达了格式偏好
                update["custom_instructions"] = user_message
            elif phase == "result":
                # 用户可能在请求修订
                if user_message.strip() and not _is_accept_message(user_message):
                    update["revision_request"] = user_message
                else:
                    update["revision_request"] = ""

            self._graph.update_state(config, update)
            logger.info(f"[{session_id}] state 已更新: {list(update.keys())}")

            # 3. 如果下一个节点是 generate_note，先流式生成再恢复图
            if "generate_note" in next_nodes:
                # 流式生成笔记（用于实时预览）
                async for sse in self._streaming_generate(session_id, config):
                    yield sse

            # 4. 恢复图执行后续节点
            async for chunk in self._graph.astream(None, config):
                for node_name, state_update in chunk.items():
                    if node_name == "__interrupt__":
                        continue

                    logger.info(f"[{session_id}] 节点完成(恢复): {node_name}")

                    if isinstance(state_update, dict) and state_update.get("error"):
                        yield _sse(make_event(
                            EventType.AGENT_ERROR, session_id,
                            error=state_update["error"],
                        ))
                        return

            # 5. 检查新的中断点
            graph_state = self._graph.get_state(config)
            state_values = graph_state.values or {}
            next_nodes = graph_state.next or []

            if "present_result" in next_nodes or "handle_revision" in next_nodes:
                phase = state_values.get("phase", "")

                if phase == "result":
                    # 发送笔记结果消息
                    generated = state_values.get("generated_note", "")
                    template = state_values.get("selected_template", "outline")

                    yield _sse(chat_note_result_event(
                        session_id,
                        note_markdown=generated,
                        template_id=template,
                    ))

                    yield _sse(chat_message_event(
                        session_id,
                        role="assistant",
                        message_type="text",
                        content='这是根据你的偏好生成的笔记。你觉得怎么样？可以告诉我需要修改的地方，比如「展开第二节」、「换成大纲格式」、「增加更多例子」等。如果满意，回复「可以」或「好的」即可。',
                    ))

                elif phase == "done":
                    # 对话完成
                    generated = state_values.get("generated_note", "")
                    template = state_values.get("selected_template", "outline")

                    # 持久化笔记
                    await self._save_note(
                        content=state_values.get("content", ""),
                        template_id=template,
                        generated_note=generated,
                        session_id=session_id,
                    )

                    yield _sse(chat_note_result_event(
                        session_id,
                        note_markdown=generated,
                        template_id=template,
                    ))

                    yield _sse(chat_message_event(
                        session_id,
                        role="assistant",
                        message_type="text",
                        content="笔记已生成完毕！你可以在右侧输出历史中查看和下载。如果还需要调整，随时告诉我。",
                    ))

                    yield _sse(chat_done_event(session_id))

            elif not next_nodes:
                # 图已完成
                final_values = graph_state.values or {}
                generated = final_values.get("generated_note", "")
                template = final_values.get("selected_template", "outline")

                await self._save_note(
                    content=final_values.get("content", ""),
                    template_id=template,
                    generated_note=generated,
                    session_id=session_id,
                )

                yield _sse(chat_note_result_event(
                    session_id,
                    note_markdown=generated,
                    template_id=template,
                ))
                yield _sse(chat_done_event(session_id))

        except Exception as e:
            logger.error(f"[{session_id}] resume 执行异常: {e}", exc_info=True)
            yield _sse(make_event(
                EventType.AGENT_ERROR, session_id,
                error=str(e),
            ))

    # ================================================================
    # 内部：流式生成
    # ================================================================

    async def _streaming_generate(
        self,
        session_id: str,
        config: dict,
    ) -> AsyncIterator[str]:
        """
        流式执行 LLM 生成笔记。

        绕过 LLMService.generate()（会缓存整条响应），
        直接调用 generate_stream() 获取逐 token 输出，
        每个 token 作为 chat_stream_chunk 事件推送。
        """
        graph_state = self._graph.get_state(config)
        state_values = graph_state.values or {}
        template_id = state_values.get("selected_template", "outline")
        revision_count = state_values.get("revision_count", 0)
        revision_request = state_values.get("revision_request", "")

        # 构建 prompt
        from app.prompts.note import NOTE_PROMPTS
        from app.agent.chat_graph import _build_enriched_user_message, _build_revision_user_message

        if revision_request and revision_count > 0:
            system_prompt = _load_revision_system_prompt(
                revision_request, state_values.get("generated_note", ""), revision_count
            )
            user_message = _build_revision_user_message(state_values)
        else:
            system_prompt = NOTE_PROMPTS.get(template_id, NOTE_PROMPTS.get("outline", ""))
            user_message = _build_enriched_user_message(state_values)

        # 流式调用 LLM
        accumulated = ""
        try:
            async for token in self._llm_service.generate_stream(
                LLMRequest(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    temperature=0.7,
                    max_tokens=4096,
                )
            ):
                accumulated += token
                yield _sse(chat_stream_chunk_event(
                    session_id,
                    chunk=token,
                    accumulated=accumulated,
                ))

            # 将生成结果写入图状态
            self._graph.update_state(config, {"generated_note": accumulated})
            logger.info(f"[{session_id}] 流式生成完成: {len(accumulated)} 字符")

        except Exception as e:
            logger.error(f"[{session_id}] 流式生成失败: {e}")
            yield _sse(make_event(
                EventType.AGENT_ERROR, session_id,
                error=f"笔记生成失败: {e}",
            ))

    # ================================================================
    # 内部：持久化
    # ================================================================

    async def _save_note(
        self,
        content: str,
        template_id: str,
        generated_note: str,
        session_id: str,
    ) -> None:
        """将生成的笔记持久化到 NoteRepository（静默失败，不影响主流程）。"""
        if self._note_repo is None or not generated_note:
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
# 辅助函数
# ============================================================

def _is_accept_message(message: str) -> bool:
    """判断用户消息是否表示接受/完成。"""
    accept_keywords = ["可以", "好的", "好", "ok", "OK", "行", "满意", "没问题", "就这样", "完成", "结束", "done", "yes", "y"]
    msg_lower = message.strip().lower()
    return any(kw in msg_lower for kw in accept_keywords)


def _build_design_framework_fallback(state_values: dict) -> dict:
    """手动构建设计框架（当 present_design 节点未执行时使用）。"""
    topics = state_values.get("main_topics", [])
    return {
        "content_summary": (
            f"内容类型为 {state_values.get('content_type', '未知')}，"
            f"复杂度 {state_values.get('complexity', '中等')}，"
            f"共 {state_values.get('parsed_total_words', 0)} 字，"
            f"预估学习时间 {state_values.get('estimated_study_time_minutes', 30)} 分钟"
        ),
        "topics": [
            {
                "name": t.get("name", ""),
                "coverage": t.get("coverage", ""),
                "subtopics": t.get("subtopics", []),
            }
            for t in topics[:5]
        ],
        "suggested_format": state_values.get("selected_template", "outline"),
        "format_reasoning": "根据内容结构推荐此格式",
        "alternative_formats": ["summary", "cornell", "qa"],
        "formatting_suggestions": [
            "使用多级标题组织知识结构",
            "加粗关键术语和重要概念",
            "使用列表整理并列知识点",
        ],
        "user_prompts": [
            "你想重点关注哪些主题？",
            "你是否希望添加学习批注和复习提示？",
            "你是否希望使用颜色强调来区分不同类型的知识点？",
        ],
    }


def _build_design_message(state_values: dict, design_framework: dict) -> str:
    """构建设计框架的友好消息。"""
    topics_list = "\n".join(
        f"- **{t.get('name', '')}**：{t.get('coverage', '')}"
        for t in design_framework.get("topics", [])[:5]
    )
    complexity = state_values.get("complexity", "中等")
    study_time = state_values.get("estimated_study_time_minutes", 30)
    suggested = design_framework.get("suggested_format", "outline")

    format_names = {"outline": "大纲笔记", "summary": "详细摘要", "cornell": "康奈尔笔记", "qa": "问答笔记"}
    fmt_name = format_names.get(suggested, suggested)

    return (
        f"我已经分析了你的学习内容，以下是分析结果：\n\n"
        f"📊 **内容概览**\n"
        f"- 类型：{state_values.get('content_type', '未知')}\n"
        f"- 复杂度：{complexity}\n"
        f"- 预估学习时间：{study_time} 分钟\n"
        f"- 字数：{state_values.get('parsed_total_words', 0)} 字\n\n"
        f"🎯 **核心主题**\n{topics_list}\n\n"
        f"📝 **格式建议**\n"
        f"我推荐使用 **{fmt_name}** 格式。请从下方选择一个格式，"
        f"然后告诉我你的偏好（如重点主题、是否添加批注、颜色强调等）。"
    )


def _load_revision_system_prompt(revision_request: str, previous_note: str, count: int) -> str:
    """加载修订系统 prompt。"""
    return f"""你是一位专业的学习笔记编辑。用户对你之前生成的笔记提出了修改意见。

修改要求：{revision_request}

之前的笔记：
{previous_note[:2000]}

修改次数：第 {count} 次

请根据修改要求重新生成笔记。注意：
1. 只修改用户要求的部分，保留其他内容不变
2. 如果用户要求"展开某部分"，请增加细节
3. 如果用户要求"更换格式"，请完全重新组织
4. 如果要求不明确，按最合理的理解处理
5. 保持高质量的中文输出

请直接输出修改后的完整 Markdown 笔记。"""


# ============================================================
# SSE 格式化
# ============================================================

def _sse(event) -> str:
    """将一个 AgentEvent 格式化为 SSE 协议字符串。"""
    data = json.dumps(
        {"type": event.type.value, "data": event.data},
        ensure_ascii=False,
    )
    return f"event: {event.type.value}\ndata: {data}\n\n"
