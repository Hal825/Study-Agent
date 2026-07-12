"""Skill Layer —— 可组合的能力单元，介于 Agent 和 Tool 之间。"""

from app.skills.base import BaseSkill, SkillContext, SkillResult
from app.skills.registry import SkillRegistry
from app.skills.note_gen import NoteGenerationSkill

__all__ = [
    "BaseSkill",
    "SkillContext",
    "SkillResult",
    "SkillRegistry",
    "NoteGenerationSkill",
]
