"""
简单日志模块
============
仅记录 Agent 调度和工具调用情况，打印到控制台。
"""

import time
from typing import Optional


class SimpleLogger:
    """简单日志记录器"""

    def __init__(self):
        self._logs: list[dict] = []

    def log_agent_start(self, user_message: str, model: str = ""):
        """记录 Agent 开始处理"""
        entry = {
            "type": "agent",
            "event": "start",
            "message": f"🤖 Agent 开始处理: {user_message[:50]}{'...' if len(user_message) > 50 else ''}",
            "model": model,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Agent] {entry['message']}")
        if model:
            print(f"[Agent] 使用模型: {model}")

    def log_tool_call(self, tool_name: str, args: dict):
        """记录工具调用"""
        args_preview = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
        entry = {
            "type": "tool",
            "event": "call",
            "tool": tool_name,
            "message": f"🔧 调用工具: {tool_name}({args_preview})",
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Tool] {entry['message']}")

    def log_tool_result(self, tool_name: str, result: str, cost_ms: int):
        """记录工具执行结果"""
        # 截取结果的前 100 字符作为预览
        preview = result[:100].replace("\n", " ")
        if len(result) > 100:
            preview += "..."
        entry = {
            "type": "tool",
            "event": "result",
            "tool": tool_name,
            "message": f"✅ {tool_name} 执行完成 (耗时 {cost_ms}ms): {preview}",
            "cost_ms": cost_ms,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Tool] {entry['message']}")

    def log_agent_done(self, cost_ms: int, tool_calls_count: int):
        """记录 Agent 完成"""
        entry = {
            "type": "agent",
            "event": "done",
            "message": f"✅ Agent 处理完成 (总耗时 {cost_ms}ms, 工具调用 {tool_calls_count} 次)",
            "cost_ms": cost_ms,
            "tool_calls_count": tool_calls_count,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Agent] {entry['message']}")

    def log_error(self, message: str):
        """记录错误"""
        entry = {
            "type": "error",
            "message": f"❌ {message}",
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Error] {entry['message']}")

    def get_logs(self) -> list[dict]:
        """获取所有日志"""
        return self._logs.copy()

    def clear(self):
        """清空日志"""
        self._logs.clear()


# 全局单例
simple_logger = SimpleLogger()