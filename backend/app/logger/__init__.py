"""
简单日志模块
============
仅记录 Agent 调度和工具调用情况，打印到控制台（stderr，与 uvicorn 日志同流）。
"""

import sys
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
            "message": f"[START] Agent processing: {user_message[:50]}{'...' if len(user_message) > 50 else ''}",
            "model": model,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Agent] {entry['message']}", flush=True, file=sys.stderr)
        if model:
            print(f"[Agent] 使用模型: {model}", flush=True, file=sys.stderr)

    def log_tool_call(self, tool_name: str, args: dict):
        """记录工具调用"""
        args_preview = ", ".join(f"{k}={str(v)[:30]}" for k, v in args.items())
        entry = {
            "type": "tool",
            "event": "call",
            "tool": tool_name,
            "message": f"[CALL] Tool: {tool_name}({args_preview})",
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Tool] {entry['message']}", flush=True, file=sys.stderr)

    def log_tool_result(self, tool_name: str, result: str, cost_ms: int):
        """记录工具执行结果"""
        preview = result[:100].replace("\n", " ")
        if len(result) > 100:
            preview += "..."
        entry = {
            "type": "tool",
            "event": "result",
            "tool": tool_name,
            "message": f"[OK] {tool_name} done ({cost_ms}ms): {preview}",
            "cost_ms": cost_ms,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Tool] {entry['message']}", flush=True, file=sys.stderr)

    def log_agent_done(self, cost_ms: int, tool_calls_count: int):
        """记录 Agent 完成"""
        entry = {
            "type": "agent",
            "event": "done",
            "message": f"[OK] Agent done (total {cost_ms}ms, tool calls: {tool_calls_count})",
            "cost_ms": cost_ms,
            "tool_calls_count": tool_calls_count,
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Agent] {entry['message']}", flush=True, file=sys.stderr)

    def log_error(self, message: str):
        """记录错误"""
        entry = {
            "type": "error",
            "message": f"[ERROR] {message}",
            "timestamp": time.time(),
        }
        self._logs.append(entry)
        print(f"[Error] {entry['message']}", flush=True, file=sys.stderr)

    def get_logs(self) -> list[dict]:
        """获取所有日志"""
        return self._logs.copy()

    def clear(self):
        """清空日志"""
        self._logs.clear()


# 全局单例
simple_logger = SimpleLogger()
