"""
Skill 注册中心 —— 按 skill_id 管理全部 Skill 实例。

与 ToolRegistry 风格一致。
"""

import logging
from typing import Optional

from app.skills.base import BaseSkill

logger = logging.getLogger("skills.registry")


class SkillRegistry:
    """
    Skill 注册中心。

    用法:
        reg = SkillRegistry()
        reg.register(NoteGenerationSkill())
        skill = reg.get("note_gen")
    """

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """注册一个 Skill 实例。"""
        if not skill.skill_id:
            raise ValueError(f"Skill 缺少 skill_id: {type(skill).__name__}")
        if skill.skill_id in self._skills:
            raise ValueError(f"Skill [{skill.skill_id}] 已注册，不允许重复")
        self._skills[skill.skill_id] = skill
        logger.info(f"注册 Skill: {skill.skill_id} ({type(skill).__name__})")

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """按 skill_id 获取 Skill，不存在返回 None。"""
        return self._skills.get(skill_id)

    def list_all(self) -> list[BaseSkill]:
        """获取所有已注册 Skill。"""
        return list(self._skills.values())

    def get_names(self) -> list[str]:
        """获取所有 Skill 名称列表。"""
        return list(self._skills.keys())

    def get_by_tool(self, tool_name: str) -> list[BaseSkill]:
        """查找依赖指定 Tool 的所有 Skill。"""
        return [
            s for s in self._skills.values()
            if tool_name in s.required_tools()
        ]
