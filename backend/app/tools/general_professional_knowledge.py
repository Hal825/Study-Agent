"""
通用专业知识获取工具
====================
工具标识：general_professional_knowledge
底层 LLM：deepseek-v4-pro（通过 llm.deepseek_client.DeepSeekClient 调用）

定位：纯素材供给工具，不直接回复用户，输出内容仅作为其他业务工具的知识输入源。
"""

import re
import logging
from typing import Literal

from app.llm.deepseek_client import DeepSeekClient
from app.llm.models import DEEPSEEK_V4_PRO
from app.prompts.general_professional_knowledge import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------- 常量 ----------
VALID_DETAIL_LEVELS = {"simple", "standard", "deep"}

# 本工具使用的 DeepSeek 模型（从 llm/models.py 统一引用）
DS_MODEL = DEEPSEEK_V4_PRO

# 固化超参（不可修改）
LLM_PARAMS = {
    "temperature": 0.1,
    "top_p": 0.8,
    "max_tokens": 32768,
    "presence_penalty": 0.0,
    "frequency_penalty": 0.0,
}


# ---------- 返回结构 ----------
class KnowledgeResult:
    """工具返回结构"""

    def __init__(
        self,
        professional_knowledge: str = "",
        error: str | None = None,
        low_confidence: bool = False,
    ):
        self.professional_knowledge = professional_knowledge
        self.error = error
        self.low_confidence = low_confidence

    def to_dict(self) -> dict:
        result = {
            "professional_knowledge": self.professional_knowledge,
        }
        if self.error:
            result["error"] = self.error
        if self.low_confidence:
            result["low_confidence_warning"] = (
                "素材大量标注【无权威教材支撑】，建议更换补充工具"
            )
        return result


# ---------- 内部辅助函数 ----------
def _validate_params(
    core_topic: str, domain_scope: str, detail_level: str
) -> str | None:
    """
    参数校验，返回错误信息；校验通过返回 None。
    """
    if not core_topic or not core_topic.strip():
        return "参数缺失：core_topic 不能为空"
    if not domain_scope or not domain_scope.strip():
        return "参数缺失：domain_scope 不能为空"
    if detail_level not in VALID_DETAIL_LEVELS:
        return (
            f"参数非法：detail_level 仅允许 {VALID_DETAIL_LEVELS}，"
            f"当前值：{detail_level!r}"
        )
    return None


def _clean_output(raw_text: str) -> tuple[str, bool]:
    """
    清洗 LLM 输出：
    1. 剔除开头/结尾的闲聊、引导话术、总结句
    2. 检测是否大量标注【无权威教材支撑】
    返回 (清洗后文本, 是否低置信度)
    """
    text = raw_text.strip()

    # 剔除常见开头话术（如 "好的"、"以下是"、"根据您的需求" 等）
    text = re.sub(
        r"^(好的[，,。.]?\s*|以下是.*?[：:]\s*|根据您.*?[：:]\s*|当然[，,。.]?\s*)",
        "",
        text,
        flags=re.MULTILINE,
    )

    # 剔除结尾总结句（如 "希望以上内容..."、"以上就是..." 等）
    text = re.sub(
        r"(希望以上.*[。.]|以上就是.*[。.]|如需进一步.*[。.]|如果您还有.*[。.]?)\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )

    text = text.strip()

    # 检测低置信度：统计【无权威教材支撑】出现次数
    no_source_count = text.count("无权威教材支撑")
    total_lines = len([line for line in text.split("\n") if line.strip()])
    low_confidence = (
        total_lines > 0 and no_source_count / max(total_lines, 1) > 0.3
    )

    return text, low_confidence


# ---------- 工具主函数 ----------
async def general_professional_knowledge(
    core_topic: str,
    domain_scope: str,
    detail_level: Literal["simple", "standard", "deep"],
) -> KnowledgeResult:
    """
    通用专业知识获取工具

    Args:
        core_topic: 核心查询主题（精准专业名词，如：二叉树、洛必达法则）
        domain_scope: 所属学科/领域（如：计算机408数据结构、高等数学）
        detail_level: 内容深度（simple / standard / deep）

    Returns:
        KnowledgeResult: 包含 professional_knowledge 字段的结构化结果
    """
    # 步骤 1：参数校验
    error = _validate_params(core_topic, domain_scope, detail_level)
    if error:
        return KnowledgeResult(error=error)

    # 步骤 2：组装 Prompt & 调用 LLM
    system_prompt = SYSTEM_PROMPT.format(
        core_topic=core_topic,
        domain_scope=domain_scope,
        detail_level=detail_level,
    )

    try:
        ds = DeepSeekClient(model=DS_MODEL)
        raw_text = await ds.chat(
            message=(
                f"请生成关于「{core_topic}」的专业知识素材，"
                f"领域：{domain_scope}，深度：{detail_level}。"
            ),
            system_prompt=system_prompt,
            **LLM_PARAMS,
        )

        if not raw_text.strip():
            return KnowledgeResult(
                professional_knowledge="该领域暂无标准化专业理论素材"
            )

        # 步骤 3：结果清洗
        cleaned_text, low_confidence = _clean_output(raw_text)

        return KnowledgeResult(
            professional_knowledge=cleaned_text,
            low_confidence=low_confidence,
        )

    except Exception as e:
        # 步骤 4：异常兜底
        logger.error("general_professional_knowledge 调用失败: %s", str(e))
        return KnowledgeResult(
            professional_knowledge="",
            error=f"LLM 调用异常：{str(e)}",
        )


# ---------- Function Call 描述（供 Agent 调度使用） ----------
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "general_professional_knowledge",
        "description": (
            "仅生成指定学科主题的客观专业知识文本，仅作为其他工具的知识素材源，"
            "无法独立回答用户问题；仅当流程需要底层专业理论素材时调用，"
            "不单独用于回复用户。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "core_topic": {
                    "type": "string",
                    "description": (
                        "核心查询主题，精准专业名词，如：二叉树、洛必达法则、进程调度；"
                        "禁止问句、模糊长句"
                    ),
                },
                "domain_scope": {
                    "type": "string",
                    "description": (
                        "所属学科/领域，自定义文本，"
                        "如：计算机408数据结构、高等数学、西方经济学"
                    ),
                },
                "detail_level": {
                    "type": "string",
                    "enum": ["simple", "standard", "deep"],
                    "description": (
                        "内容深度：simple(基础精简)、standard(标准完整)、deep(深度重难点)"
                    ),
                },
            },
            "required": ["core_topic", "domain_scope", "detail_level"],
        },
    },
}