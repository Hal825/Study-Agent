"""
专业试题生成工具
================
工具标识：exam_generate_tool
底层 LLM：qwq-plus（通过 llm.qwen_client.QwenClient 调用）

定位：纯试题素材生成工具，基于上游专业知识素材产出配套试题、答案与解析，
      不直接面向用户输出，仅作为下游回答组织工具的输入素材。
"""

import re
import logging
from typing import Literal

from app.llm.qwen_client import QwenClient
from app.llm.models import QWQ_PLUS
from app.prompts.exam_generate_tool import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------- 常量 ----------
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
DEFAULT_DIFFICULTY = "medium"

# 本工具使用的 Qwen 模型（从 llm/models.py 统一引用）
QWEN_MODEL = QWQ_PLUS

# 固化超参（不可修改）
LLM_PARAMS = {
    "temperature": 0.1,
    "top_p": 0.8,
    "max_tokens": 4096,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}


# ---------- 返回结构 ----------
class ExamResult:
    """工具返回结构"""

    def __init__(
        self,
        exam_raw_data: str = "",
        error: str | None = None,
    ):
        self.exam_raw_data = exam_raw_data
        self.error = error

    def to_dict(self) -> dict:
        result = {
            "exam_raw_data": self.exam_raw_data,
        }
        if self.error:
            result["error"] = self.error
        return result


# ---------- 内部辅助函数 ----------
def _validate_params(
    knowledge_source: str,
    exam_difficulty: str,
) -> tuple[str | None, str]:
    """
    参数校验：
    1. knowledge_source 非空，缺失返回错误
    2. exam_difficulty 非法值自动重置为 medium
    返回 (错误信息, 最终难度值)
    """
    if not knowledge_source or not knowledge_source.strip():
        return "参数缺失：knowledge_source 不能为空，必须传入上游专业知识素材", DEFAULT_DIFFICULTY

    if exam_difficulty not in VALID_DIFFICULTIES:
        logger.warning(
            "exam_difficulty 参数非法：%r，自动重置为 %s",
            exam_difficulty,
            DEFAULT_DIFFICULTY,
        )
        return None, DEFAULT_DIFFICULTY

    return None, exam_difficulty


def _clean_output(raw_text: str) -> str:
    """
    清洗 LLM 输出：
    1. 剔除开头/结尾的闲聊、引导话术、总结句
    2. 仅保留标准化试题原始素材
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
async def exam_generate_tool(
    knowledge_source: str,
    exam_demand: str = "",
    exam_difficulty: Literal["easy", "medium", "hard"] = "medium",
) -> ExamResult:
    """
    专业试题生成工具

    Args:
        knowledge_source: Tool1 输出的完整结构化专业知识素材（必填）
        exam_demand: 用户自定义试题要求（题型、题量、考察方向等），空字符串表示无额外定制
        exam_difficulty: 试题难度（easy / medium / hard），默认 medium

    Returns:
        ExamResult: 包含 exam_raw_data 字段的结构化结果
    """
    # 步骤 1：参数校验
    error, final_difficulty = _validate_params(knowledge_source, exam_difficulty)
    if error:
        return ExamResult(error=error)

    # 步骤 2：组装 Prompt & 调用 LLM
    system_prompt = SYSTEM_PROMPT.format(
        knowledge_source=knowledge_source,
        exam_demand=exam_demand if exam_demand else "无",
        exam_difficulty=final_difficulty,
    )

    try:
        qwen = QwenClient(model=QWEN_MODEL)
        raw_text = await qwen.chat(
            message=(
                f"请基于传入的专业知识素材生成配套试题，"
                f"难度：{final_difficulty}，"
                f"自定义需求：{exam_demand if exam_demand else '无'}。"
            ),
            system_prompt=system_prompt,
            **LLM_PARAMS,
        )

        if not raw_text.strip():
            return ExamResult(
                exam_raw_data="该知识素材暂无可生成的配套试题"
            )

        # 步骤 3：结果清洗
        cleaned_text = _clean_output(raw_text)

        return ExamResult(exam_raw_data=cleaned_text)

    except Exception as e:
        # 步骤 4：异常兜底
        logger.error("exam_generate_tool 调用失败: %s", str(e))
        return ExamResult(
            exam_raw_data="",
            error=f"LLM 调用异常：{str(e)}",
        )


# ---------- Function Call 描述（供 Agent 调度使用） ----------
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "exam_generate_tool",
        "description": (
            "基于上游专业知识素材生成配套试题、答案与完整解析思路；"
            "支持传入指定试题难度，无难度参数默认生成中等难度题目，"
            "同时支持自定义出题要求，所有题目严格贴合素材内权威知识点。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "knowledge_source": {
                    "type": "string",
                    "description": (
                        "Tool1（general_professional_knowledge）输出的完整结构化专业知识素材，"
                        "携带定义、原理、权威参考出处，是出题唯一依据"
                    ),
                },
                "exam_demand": {
                    "type": "string",
                    "description": (
                        "用户自定义试题要求；用于指定题型、题量、考察方向、出题形式等，"
                        "为空则无额外定制约束"
                    ),
                    "default": "",
                },
                "exam_difficulty": {
                    "type": "string",
                    "enum": ["easy", "medium", "hard"],
                    "description": (
                        "试题难度：easy(简单)、medium(中等)、hard(困难)；"
                        "不传该参数则固定生成中等难度题目"
                    ),
                    "default": "medium",
                },
            },
            "required": ["knowledge_source"],
        },
    },
}