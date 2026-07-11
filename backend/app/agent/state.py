"""
Agent 状态定义 —— LangGraph 状态图的 State Schema。

所有节点读写同一个 NoteAgentState 实例，
LangGraph 自动管理 checkpoint 和状态传递。
"""

from typing import Annotated, Any, Optional, TypedDict

from langgraph.graph.message import add_messages


class SectionInfo(TypedDict, total=False):
    """单个章节信息。"""
    heading: str
    level: int
    content: str
    start_line: int


class EntityInfo(TypedDict, total=False):
    """单个知识实体。"""
    name: str
    category: str
    importance: str
    context: str
    related: list[str]


class TopicInfo(TypedDict, total=False):
    """核心主题。"""
    name: str
    coverage: str
    subtopics: list[str]


class OutlineItem(TypedDict, total=False):
    """大纲条目。"""
    heading: str
    level: int
    key_points: list[str]


class NoteAgentState(TypedDict, total=False):
    """
    笔记生成 Agent 的状态。

    贯穿整个 LangGraph 执行过程，
    每个节点按需读写其中的字段。
    """

    # ---- 用户输入 ----
    content: str
    template_id: str
    session_id: str

    # ---- 中间结果（各 Tool 产出） ----
    # ContentParser 产出
    parsed_title: str
    parsed_sections: list[SectionInfo]
    parsed_total_words: int
    parsed_language: str

    # EntityExtractor 产出
    entities: list[EntityInfo]
    key_concepts: list[str]

    # StructureAnalyzer 产出
    content_type: str
    hierarchy_depth: int
    main_topics: list[TopicInfo]
    suggested_outline: list[OutlineItem]
    complexity: str
    estimated_study_time_minutes: int

    # ---- 最终输出 ----
    generated_note: str

    # ---- 控制字段 ----
    stage: str           # 当前阶段，用于前端 SSE 展示
    error: str           # 错误信息
    human_confirmed: bool  # 用户是否已确认模板选择
