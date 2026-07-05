"""
StudyAgent
==========
学习 Agent —— 最小逻辑闭环。

职责：
  1. 理解用户问题（意图识别 + 参数抽取）
  2. 调度工具（通过 DeepSeek function calling 自主决策调用顺序）
  3. 获取工具结果（多轮 tool_calls 循环，处理工具间数据依赖）
  4. 推送最终答案（工具循环结束后，LLM 生成面向用户的最终回复）

底层 LLM：deepseek-v4-pro（通过 llm.deepseek_client.DeepSeekClient 调用）
可用工具：
  - general_professional_knowledge  （专业知识素材供给）
  - exam_generate_tool              （配套试题生成）
  - answer_organize_tool            （回答形态组织渲染）
"""

import json
import logging
import os
import time
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

2. exam_generate_tool
   - 作用：基于上游知识素材生成配套试题、答案与解析
   - 定位：纯试题素材生成，不直接回复用户
   - 参数：knowledge_source(必填，来自工具1的输出)、exam_demand(可选)、exam_difficulty(easy/medium/hard)

3. answer_organize_tool
   - 作用：将知识素材、试题素材按指定形态组织为用户可读回答
   - 定位：唯一面向终端用户的内容出口
   - 参数：render_mode(simple_know/dialog_qa/knowledge_exercise/exam_summary/quick_answer)、
          knowledge_source(必填)、exam_source(knowledge_exercise模式必填)、user_original_query(必填)

调度原则：
- 工具间存在数据依赖：工具2 需要 工具1 的输出作为 knowledge_source；
  工具3 需要 工具1 的输出作为 knowledge_source，knowledge_exercise 模式还需要 工具2 的输出作为 exam_source。
- 因此典型调用链路为：工具1 → (可选)工具2 → 工具3。
- 你需要自主决策调用哪些工具、以何种顺序调用、传入什么参数。
- 工具调用的参数值需要你从用户问题中抽取或推断。
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

    # ---------- 工具执行 ----------
    async def _execute_tool(self, name: str, arguments: dict) -> str:
        """
        执行指定工具，返回 JSON 字符串形式的结果（用于回填 tool 消息）。
        """
        start_time = time.time()
        tool_fn = self.tool_registry.get(name)

        if not tool_fn:
            simple_logger.log_error(f"未知工具：{name}")
            return json.dumps(
                {"error": f"未知工具：{name}"}, ensure_ascii=False
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