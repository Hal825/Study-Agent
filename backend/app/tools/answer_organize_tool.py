"""
回答形态组织渲染工具
=====================
工具标识：answer_organize_tool
底层 LLM：deepseek-v4-flash（通过 llm.deepseek_client.DeepSeekClient 调用）

定位：统一对外输出渲染层，不生产知识、不生成题目，
      仅对上游两份素材做排版重组、语气适配、分形态输出，
      是唯一面向终端用户的内容出口。
"""

import re
import logging
from typing import Literal

from app.llm.deepseek_client import DeepSeekClient
from app.llm.models import DEEPSEEK_V4_FLASH
from app.prompts.answer_organize_tool import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------- 常量 ----------
VALID_RENDER_MODES = {
    "simple_know",
    "dialog_qa",
    "knowledge_exercise",
    "exam_summary",
    "quick_answer",
}

# 习题模式：必须同时传入 knowledge_source + exam_source
EXAM_REQUIRED_MODES = {"knowledge_exercise"}

# 本工具使用的 DeepSeek 模型（从 llm/models.py 统一引用）
LLM_MODEL = DEEPSEEK_V4_FLASH

# 固化超参（不可修改）
LLM_PARAMS = {
    "temperature": 0.1,
    "top_p": 0.8,
    "max_tokens": 8192,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}


# ---------- 返回结构 ----------
class AnswerResult:
    """工具返回结构"""

    def __init__(
        self,
        organized_user_reply: str = "",
        error: str | None = None,
    ):
        self.organized_user_reply = organized_user_reply
        self.error = error

    def to_dict(self) -> dict:
        result = {
            "organized_user_reply": self.organized_user_reply,
        }
        if self.error:
            result["error"] = self.error
        return result


# ---------- 内部辅助函数 ----------
def _validate_params(
    render_mode: str,
    knowledge_source: str,
    exam_source: str,
) -> str | None:
    """
    参数校验：
    1. render_mode 必须属于指定枚举值
    2. knowledge_source 全模式最低必填，为空直接拦截
    3. render_mode=knowledge_exercise 时，exam_source 升级为必填
    返回错误信息；校验通过返回 None。
    """
    if render_mode not in VALID_RENDER_MODES:
        return (
            f"参数非法：render_mode 仅允许 {VALID_RENDER_MODES}，"
            f"当前值：{render_mode!r}"
        )

    if not knowledge_source or not knowledge_source.strip():
        return "参数缺失：knowledge_source 不能为空，所有渲染模式均必备底层知识素材"

    if render_mode in EXAM_REQUIRED_MODES:
        if not exam_source or not exam_source.strip():
            return (
                "资源缺失：render_mode=knowledge_exercise 模式下 exam_source 必填，"
                "缺少试题素材无法渲染知识讲解+配套试题形态"
            )

    return None


def _clean_output(raw_text: str) -> str:
    """
    清洗 LLM 输出：
    1. 剔除开头/结尾的闲聊、引导话术、总结句
    2. 仅保留规整学习内容
    """
    text = raw_text.strip()

    # 剔除常见开头话术
    text = re.sub(
        r"^(好的[，,。.]?\s*|以下是.*?[：:]\s*|根据您.*?[：:]\s*|当然[，,。.]?\s*)",
        "",
        text,
        flags=re.MULTILINE,
    )

    # 剔除结尾总结句
    text = re.sub(
        r"(希望以上.*[。.]|以上就是.*[。.]|如需进一步.*[。.]|如果您还有.*[。.]?)\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    return text.strip()


# ---------- 工具主函数 ----------
async def answer_organize_tool(
    render_mode: Literal[
        "simple_know",
        "dialog_qa",
        "knowledge_exercise",
        "exam_summary",
        "quick_answer",
    ],
    knowledge_source: str,
    exam_source: str = "",
    user_original_query: str = "",
) -> AnswerResult:
    """
    回答形态组织渲染工具

    Args:
        render_mode: 渲染模式（5 种固定形态）
        knowledge_source: Tool1 返回的完整结构化专业知识素材（全模式必填）
        exam_source: Tool3 输出的原始试题素材（knowledge_exercise 模式必填，其余可选）
        user_original_query: 用户原始提问，用于适配讲解语气

    Returns:
        AnswerResult: 包含 organized_user_reply 字段的结构化结果
    """
    # 步骤 1：入参资源校验
    error = _validate_params(render_mode, knowledge_source, exam_source)
    if error:
        return AnswerResult(error=error)

    # 步骤 2：组装 Prompt & 调用 LLM
    system_prompt = SYSTEM_PROMPT.format(
        render_mode=render_mode,
        knowledge_source=knowledge_source,
        exam_source=exam_source if exam_source.strip() else "无",
        user_original_query=user_original_query if user_original_query.strip() else "无",
    )

    try:
        deepseek = DeepSeekClient(model=LLM_MODEL)
        raw_text = await deepseek.chat(
            message=(
                f"请按 {render_mode} 模式组织渲染学习回答，"
                f"用户原始提问：{user_original_query if user_original_query.strip() else '无'}。"
            ),
            system_prompt=system_prompt,
            **LLM_PARAMS,
        )

        if not raw_text.strip():
            return AnswerResult(
                organized_user_reply="暂无法基于当前素材组织可读回答"
            )

        # 步骤 3：结果清洗
        cleaned_text = _clean_output(raw_text)

        return AnswerResult(organized_user_reply=cleaned_text)

    except Exception as e:
        # 步骤 4：异常兜底
        logger.error("answer_organize_tool 调用失败: %s", str(e))
        return AnswerResult(
            organized_user_reply="",
            error=f"LLM 调用异常：{str(e)}",
        )


# ---------- Function Call 描述（供 Agent 调度使用） ----------
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "answer_organize_tool",
        "description": (
            "接收底层专业知识素材、可选试题素材，按指定格式组装为用户可读学习回答；"
            "所有对外回复统一由本工具渲染，无知识素材无法运行，"
            "知识+试题模式必须同时传入试题素材。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "render_mode": {
                    "type": "string",
                    "enum": [
                        "simple_know",
                        "dialog_qa",
                        "knowledge_exercise",
                        "exam_summary",
                        "quick_answer",
                    ],
                    "description": (
                        "渲染模式：simple_know(纯知识讲解)、dialog_qa(一问一答对话)、"
                        "knowledge_exercise(知识讲解+配套试题)、"
                        "exam_summary(考点精讲+易错总结)、quick_answer(极简答疑)"
                    ),
                },
                "knowledge_source": {
                    "type": "string",
                    "description": (
                        "Tool1（general_professional_knowledge）返回的完整结构化专业知识素材，"
                        "包含定义、原理、权威参考出处，所有渲染模式必备底层素材"
                    ),
                },
                "exam_source": {
                    "type": "string",
                    "description": (
                        "Tool3（exam_generate_tool）输出的原始试题素材，"
                        "包含题干、标准答案、逐题解析；"
                        "knowledge_exercise 模式必填，其余模式可传空字符串"
                    ),
                    "default": "",
                },
                "user_original_query": {
                    "type": "string",
                    "description": "用户原始提问，用于适配讲解语气、贴合用户真实学习诉求",
                },
            },
            "required": ["render_mode", "knowledge_source", "user_original_query"],
        },
    },
}