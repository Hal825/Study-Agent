"""
StudyAgent
==========
学习 Agent —— 最小逻辑闭环。

职责：
  1. 理解用户问题（意图识别 + 参数抽取）
  2. 会话创建时立即预取专业知识（general_professional_knowledge），缓存结果
  3. 调度工具（通过 DeepSeek function calling 自主决策调用顺序）
  4. 获取工具结果（多轮 tool_calls 循环，处理工具间数据依赖）
  5. 推送最终答案（工具循环结束后，LLM 生成面向用户的最终回复）

底层 LLM：deepseek-v4-pro（通过 llm.deepseek_client.DeepSeekClient 调用）
可用工具：
  - general_professional_knowledge  （专业知识素材供给，会话创建时预取+缓存）
  - exam_generate_tool              （配套试题生成，可从缓存自动注入 knowledge_source）
  - answer_organize_tool            （回答形态组织渲染，可从缓存自动注入 knowledge_source）
"""

import json
import logging
import os
import time
import asyncio
from typing import AsyncIterator

from app.llm import DeepSeekClient
from app.tools import (
    general_professional_knowledge,
    exam_generate_tool,
    answer_organize_tool,
)
from app.tools.general_professional_knowledge import TOOL_SCHEMA as TOOL1_SCHEMA
from app.tools.exam_generate_tool import TOOL_SCHEMA as TOOL2_SCHEMA
from app.tools.answer_organize_tool import TOOL_SCHEMA as TOOL3_SCHEMA
from app.logger import simple_logger

logger = logging.getLogger(__name__)

# ---------- Agent System Prompt ----------
SYSTEM_PROMPT = """你是 Study Agent，一个智能学习助手。

你拥有以下三个工具，必须通过 function calling 调度它们来回答用户的学习问题：

1. general_professional_knowledge
   - 作用：获取指定学科主题的客观专业知识素材（定义、原理、权威出处）
   - 定位：纯素材供给，不直接回复用户
   - 参数：core_topic(核心主题)、domain_scope(学科领域)、detail_level(simple/standard/deep)
   - **注意：会话启动时已自动预取专业知识并缓存，你可根据需要再次调用以获取不同主题/深度的素材**

2. exam_generate_tool
   - 作用：基于上游知识素材生成配套试题、答案与解析
   - 定位：纯试题素材生成，不直接回复用户
   - 参数：knowledge_source(选填，若留空则自动使用会话缓存的专业知识)、exam_demand(可选)、exam_difficulty(easy/medium/hard)

3. answer_organize_tool
   - 作用：将知识素材、试题素材按指定形态组织为用户可读回答
   - 定位：唯一面向终端用户的内容出口
   - 参数：render_mode(simple_know/dialog_qa/knowledge_exercise/exam_summary/quick_answer)、
          knowledge_source(选填，若留空则自动使用会话缓存的专业知识)、exam_source(knowledge_exercise模式选填)、user_original_query(必填)

调度原则：
- 会话创建时已自动预取专业知识并缓存，工具2和工具3的 knowledge_source 参数可留空，系统会自动注入缓存的专业知识。
- 如果你认为预取的知识已满足需求，可以直接调用工具3（跳过工具1和工具2）。
- 如需配套试题，调用工具2后再调用工具3（knowledge_exercise 模式）。
- 你仍然可以调用工具1获取不同主题或深度的知识素材。
- 当所有需要的工具调用完成后，工具3 的 organized_user_reply 即为最终回复内容，
  你可以将其作为最终答案返回给用户（可适当润色语气，但不要改变核心内容）。

回复风格：
- 友好、耐心，适当使用 emoji。
- 回答清晰有条理，必要时分点展示。
"""


# ---------- 最大工具调用轮数（防止死循环） ----------
MAX_TOOL_ROUNDS = 6


class StudyAgent:
    """
    学习 Agent —— 编排三个学习工具的最小逻辑闭环。

    通过 DeepSeek function calling 实现自主工具调度：
      用户消息 → LLM 决策(可能多次 tool_calls) → 工具执行 → 结果回填 → 最终回复
    """

    def __init__(self):
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.llm = DeepSeekClient(model=self.model)
        self.tool_schemas = [TOOL1_SCHEMA, TOOL2_SCHEMA, TOOL3_SCHEMA]
        self.tool_registry = {
            "general_professional_knowledge": general_professional_knowledge,
            "exam_generate_tool": exam_generate_tool,
            "answer_organize_tool": answer_organize_tool,
        }
        # 会话级知识缓存：会话创建时预取 general_professional_knowledge 的结果
        self._knowledge_cache: dict | None = None

    # ---------- 话题参数提取 ----------
    async def _extract_topic_params(self, user_message: str) -> dict:
        """
        从用户消息中提取 core_topic、domain_scope、detail_level。
        使用轻量 LLM 调用，返回纯 JSON。
        """
        extraction_prompt = (
            "从用户消息中提取学习意图参数，返回纯JSON（不要markdown代码块）：\n"
            '{"core_topic": "精准专业名词", "domain_scope": "所属学科/领域", "detail_level": "standard"}\n\n'
            "规则：\n"
            "- core_topic: 用户想学习的核心主题（精准专业名词，如\"二叉树\"、\"洛必达法则\"），无法判断则为空字符串\n"
            "- domain_scope: 所属学科（如\"计算机408数据结构\"、\"高等数学\"），无法判断则为空字符串\n"
            "- detail_level: 固定为 \"standard\"\n"
            "- 只返回JSON，不要任何其他文字"
        )

        try:
            raw = await self.llm.chat(
                message=user_message,
                system_prompt=extraction_prompt,
                temperature=0.0,
                max_tokens=256,
            )
            raw = raw.strip()
            # 清理可能的 markdown 代码块包裹
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
                if raw.endswith("```"):
                    raw = raw[:-3].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("话题参数提取失败：%s，将跳过预取", str(e))
            return {"core_topic": "", "domain_scope": "", "detail_level": "standard"}

    # ---------- 知识预取 ----------
    async def _prefetch_knowledge(self, user_message: str):
        """
        会话创建时立即调用 general_professional_knowledge，
        将结果缓存到 self._knowledge_cache。
        """
        params = await self._extract_topic_params(user_message)
        core_topic = params.get("core_topic", "").strip()
        domain_scope = params.get("domain_scope", "").strip()
        detail_level = params.get("detail_level", "standard")

        if not core_topic or not domain_scope:
            logger.info("未从用户消息中提取到有效话题，跳过知识预取")
            self._knowledge_cache = None
            return

        logger.info(
            "预取专业知识：topic=%s, domain=%s, level=%s",
            core_topic, domain_scope, detail_level,
        )

        try:
            result = await general_professional_knowledge(
                core_topic=core_topic,
                domain_scope=domain_scope,
                detail_level=detail_level,
            )
            self._knowledge_cache = {
                "core_topic": core_topic,
                "domain_scope": domain_scope,
                "detail_level": detail_level,
                "result": result,
            }
            logger.info("知识预取完成，已缓存")
        except Exception as e:
            logger.error("知识预取失败：%s", str(e))
            self._knowledge_cache = None

    # ---------- 工具执行 ----------
    async def _execute_tool(self, name: str, arguments: dict) -> str:
        """
        执行指定工具，返回 JSON 字符串形式的结果（用于回填 tool 消息）。

        缓存逻辑：
        - general_professional_knowledge：若缓存命中（同 topic），直接返回缓存结果
        - exam_generate_tool / answer_organize_tool：若 knowledge_source 为空，从缓存自动注入
        """
        start_time = time.time()
        tool_fn = self.tool_registry.get(name)

        if not tool_fn:
            simple_logger.log_error(f"未知工具：{name}")
            return json.dumps(
                {"error": f"未知工具：{name}"}, ensure_ascii=False
            )

        # ── 缓存注入：工具1 命中缓存则直接返回 ──
        if name == "general_professional_knowledge" and self._knowledge_cache:
            req_topic = arguments.get("core_topic", "").strip()
            cached_topic = self._knowledge_cache.get("core_topic", "")
            if req_topic and req_topic == cached_topic:
                logger.info(
                    "工具1 缓存命中（topic=%s），直接返回缓存结果", req_topic
                )
                cached_result = self._knowledge_cache["result"]
                result_dict = cached_result.to_dict()
                simple_logger.log_tool_call(name, arguments)
                simple_logger.log_tool_result(
                    name,
                    json.dumps(result_dict, ensure_ascii=False),
                    0,
                )
                return json.dumps(result_dict, ensure_ascii=False)

        # ── 缓存注入：工具2/3 自动补全 knowledge_source ──
        if name in ("exam_generate_tool", "answer_organize_tool"):
            if not arguments.get("knowledge_source") and self._knowledge_cache:
                cached_knowledge = (
                    self._knowledge_cache["result"].professional_knowledge
                )
                if cached_knowledge:
                    arguments["knowledge_source"] = cached_knowledge
                    logger.info(
                        "工具 %s 自动注入缓存知识（长度=%d）",
                        name, len(cached_knowledge),
                    )

        # 记录工具调用
        simple_logger.log_tool_call(name, arguments)

        try:
            logger.info("调用工具 %s，参数：%s", name, arguments)
            result = await tool_fn(**arguments)
            cost_time = int((time.time() - start_time) * 1000)

            # 工具返回的是 *Result 对象，统一转 dict
            if hasattr(result, "to_dict"):
                result_dict = result.to_dict()
            else:
                result_dict = {"result": str(result)}

            # ── 若工具1返回了新结果，更新缓存 ──
            if name == "general_professional_knowledge" and not result_dict.get("error"):
                self._knowledge_cache = {
                    "core_topic": arguments.get("core_topic", ""),
                    "domain_scope": arguments.get("domain_scope", ""),
                    "detail_level": arguments.get("detail_level", "standard"),
                    "result": result,
                }
                logger.info("工具1 返回新结果，已更新缓存")

            # 记录工具执行结果
            result_preview = json.dumps(result_dict, ensure_ascii=False)
            simple_logger.log_tool_result(name, result_preview, cost_time)
            logger.info("工具 %s 执行完成，耗时 %dms", name, cost_time)
            return json.dumps(result_dict, ensure_ascii=False)

        except TypeError as e:
            cost_time = int((time.time() - start_time) * 1000)
            simple_logger.log_error(f"工具 {name} 参数错误：{str(e)}")
            logger.error("工具 %s 参数错误：%s", name, str(e))
            return json.dumps(
                {"error": f"工具参数错误：{str(e)}"}, ensure_ascii=False
            )
        except Exception as e:
            cost_time = int((time.time() - start_time) * 1000)
            simple_logger.log_error(f"工具 {name} 执行异常：{str(e)}")
            logger.error("工具 %s 执行异常：%s", name, str(e))
            return json.dumps(
                {"error": f"工具执行异常：{str(e)}"}, ensure_ascii=False
            )

    # ---------- 非流式运行 ----------
    async def run(self, user_message: str) -> str:
        """
        完整运行 Agent 闭环，返回最终回复文本。
        """
        start_time = time.time()
        tool_calls_count = 0

        simple_logger.log_agent_start(user_message, self.model)

        # 步骤 0：会话创建时立即预取专业知识（后台任务，不阻塞主循环）
        asyncio.create_task(self._prefetch_knowledge(user_message))

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for round_idx in range(MAX_TOOL_ROUNDS):
            logger.info("Agent 第 %d 轮决策", round_idx + 1)
            response = await self.llm.chat_with_tools_messages(
                messages, tools=self.tool_schemas
            )
            msg = response.choices[0].message

            # 将 assistant 消息加入历史
            messages.append(msg.model_dump())

            # 无工具调用 → 最终回复
            if not msg.tool_calls:
                cost_time = int((time.time() - start_time) * 1000)
                simple_logger.log_agent_done(cost_time, tool_calls_count)
                return msg.content or ""

            # 执行所有 tool_calls
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                tool_calls_count += 1

                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                tool_result = await self._execute_tool(fn_name, fn_args)

                # 回填 tool 结果
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

        # 超出最大轮数，强制收尾
        cost_time = int((time.time() - start_time) * 1000)
        logger.warning("Agent 达到最大工具调用轮数 %d，强制收尾", MAX_TOOL_ROUNDS)
        simple_logger.log_error(f"达到最大工具调用轮数 {MAX_TOOL_ROUNDS}")

        messages.append(
            {
                "role": "user",
                "content": "（系统提示：已达到最大工具调用次数，请基于已有素材直接给出最终回答）",
            }
        )
        # 最后一轮不带 tools，强制生成文本回复
        final_response = await self.llm.chat_with_tools_messages(
            messages, tools=None
        )

        simple_logger.log_agent_done(cost_time, tool_calls_count)
        return final_response.choices[0].message.content or ""

    # ---------- 流式运行 ----------
    async def run_stream(self, user_message: str) -> AsyncIterator[str]:
        """
        流式运行 Agent 闭环。

        策略：工具调用阶段无法流式（需完整结果），因此先跑完工具循环，
        最后一轮（无 tool_calls 的最终回复）改用 chat_stream 流式输出。
        """
        start_time = time.time()
        tool_calls_count = 0

        simple_logger.log_agent_start(user_message, self.model)

        # 步骤 0：会话创建时立即预取专业知识（后台任务，不阻塞主循环）
        asyncio.create_task(self._prefetch_knowledge(user_message))

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        for round_idx in range(MAX_TOOL_ROUNDS):
            logger.info("Agent(stream) 第 %d 轮决策", round_idx + 1)
            response = await self.llm.chat_with_tools_messages(
                messages, tools=self.tool_schemas
            )
            msg = response.choices[0].message
            messages.append(msg.model_dump())

            # 无工具调用 → 这一轮的 content 即最终回复
            if not msg.tool_calls:
                cost_time = int((time.time() - start_time) * 1000)
                simple_logger.log_agent_done(cost_time, tool_calls_count)

                content = msg.content or ""
                # 简单按字符分片推送（保证流式体验）
                if content:
                    yield json.dumps(
                        {"content": content}, ensure_ascii=False
                    )
                yield json.dumps({"done": True}, ensure_ascii=False)
                return

            # 执行工具
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                tool_calls_count += 1

                try:
                    fn_args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    fn_args = {}

                tool_result = await self._execute_tool(fn_name, fn_args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

        # 超出最大轮数，强制收尾（非流式）
        cost_time = int((time.time() - start_time) * 1000)
        logger.warning(
            "Agent(stream) 达到最大工具调用轮数 %d，强制收尾",
            MAX_TOOL_ROUNDS,
        )
        simple_logger.log_error(f"达到最大工具调用轮数 {MAX_TOOL_ROUNDS}")

        messages.append(
            {
                "role": "user",
                "content": "（系统提示：已达到最大工具调用次数，请基于已有素材直接给出最终回答）",
            }
        )
        final_response = await self.llm.chat_with_tools_messages(
            messages, tools=None
        )
        content = final_response.choices[0].message.content or ""
        if content:
            yield json.dumps({"content": content}, ensure_ascii=False)
        yield json.dumps({"done": True}, ensure_ascii=False)