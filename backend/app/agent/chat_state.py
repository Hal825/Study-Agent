"""
Chat Agent 状态定义 —— 对话式笔记生成的 State Schema。

与 NoteAgentState 不同，ChatAgentState 面向多轮对话，
支持设计框架展示、用户偏好收集、流式预览和修订循环。
"""

from typing import TypedDict


class ChatMessage(TypedDict, total=False):
    """单条聊天消息（贯穿整个对话历史）。"""
    role: str           # "user" | "assistant" | "system"
    type: str           # "text" | "design_framework" | "option_cards" | "markdown_note" | "progress"
    content: str        # 主要文本内容
    data: dict | None   # 结构化载荷（卡片/选项/进度等）


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


class ChatAgentState(TypedDict, total=False):
    """
    对话式笔记生成 Agent 的状态。

    贯穿整个 LangGraph 执行过程，
    每个节点按需读写其中的字段。
    """

    # ---- 基础会话 ----
    session_id: str
    content: str                      # 用户上传的原始学习内容
    phase: str                        # "init" | "analyzing" | "design" | "generating" | "revising" | "done"

    # ---- 对话历史 ----
    messages: list[ChatMessage]       # 完整对话历史

    # ---- 中间分析结果（重用现有 Tool） ----
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

    # ---- 用户偏好（对话中收集） ----
    selected_topics: list[str]         # 用户选择聚焦的主题
    selected_template: str             # outline | summary | cornell | qa
    enable_annotations: bool           # 是否添加批注
    enable_color_emphasis: bool        # 是否加入颜色强调
    format_modifications: str          # 自由文本格式修改
    custom_instructions: str           # 用户的额外定制要求

    # ---- 最终输出 ----
    generated_note: str                # 最终生成的笔记

    # ---- 修订循环 ----
    revision_request: str              # 用户的修订请求
    revision_count: int                # 修订次数计数

    # ---- 控制字段 ----
    error: str                         # 错误信息
    human_confirmed: bool              # 用户是否已完成当前中断确认
    stream_buffer: str                 # 流式生成缓冲（用于 chat_stream_chunk 事件）
