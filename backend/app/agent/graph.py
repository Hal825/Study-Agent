"""
LangGraph 图定义 —— 笔记生成 Agent 的状态图。

图结构：
    START → parse → extract → analyze → confirm → generate → END

其中 confirm 节点配置了 interrupt_before，
执行前暂停等待前端发送用户确认。
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import NoteAgentState
from app.agent.nodes import (
    parse_content_node,
    extract_entities_node,
    analyze_structure_node,
    confirm_template_node,
    generate_note_node,
)


def build_note_graph() -> StateGraph:
    """
    构建笔记生成 Agent 的状态图。

    Returns:
        已编译的 CompiledStateGraph，可直接调用 astream() 执行。
    """
    builder = StateGraph(NoteAgentState)

    # 添加节点
    builder.add_node("parse", parse_content_node)
    builder.add_node("extract", extract_entities_node)
    builder.add_node("analyze", analyze_structure_node)
    builder.add_node("confirm", confirm_template_node)
    builder.add_node("generate", generate_note_node)

    # 连线
    builder.add_edge(START, "parse")
    builder.add_edge("parse", "extract")
    builder.add_edge("extract", "analyze")
    builder.add_edge("analyze", "confirm")
    builder.add_edge("confirm", "generate")
    builder.add_edge("generate", END)

    # 编译图（开发环境用 MemorySaver）
    checkpointer = MemorySaver()
    compiled = builder.compile(
        checkpointer=checkpointer,
        # Phase 4 启用 human-in-the-loop：
        # interrupt_before=["confirm"],
    )

    return compiled
