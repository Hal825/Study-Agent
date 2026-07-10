"""
Tool 抽象基类 —— 统一校验、超时、重试、异常、埋点。

子类只需：
1. 定义 name / description / input_schema / output_schema
2. 实现 execute() 核心逻辑
3. 按需覆写 validate() / before_run() / after_run() / on_error() 钩子

外部调用 Tool 的唯一入口是 run()，支持传入 dict 或 Pydantic 模型。
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("tools")

# 泛型类型变量
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


# ============================================================
# 统一结果
# ============================================================

class ToolStatus(str, Enum):
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    TIMEOUT = "timeout"


@dataclass
class ToolResult(Generic[OutputT]):
    """Tool 执行统一返回。"""
    status: ToolStatus
    data: Optional[OutputT] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    @classmethod
    def success(cls, data: OutputT, duration_ms: float = 0) -> "ToolResult[OutputT]":
        return cls(status=ToolStatus.SUCCESS, data=data, duration_ms=duration_ms)

    @classmethod
    def failure(cls, status: ToolStatus, error: str) -> "ToolResult[OutputT]":
        return cls(status=status, error=error)

    @property
    def ok(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，方便日志打印和前端返回。"""
        return {
            "status": self.status.value,
            "data": self.data.model_dump() if self.data is not None else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


# ============================================================
# 抽象基类
# ============================================================

class BaseTool(ABC, Generic[InputT, OutputT]):
    """
    Tool 抽象基类。

    生命周期：
        run()
         ├── input 自动解析（dict → InputT）
         ├── before_run()       # 埋点钩子
         ├── validate()         # 异步业务校验钩子
         ├── execute()          # 核心逻辑（子类实现）
         ├── after_run()        # 成功钩子
         └── on_error()         # 异常钩子
    """

    # ---- 子类必须定义 ----
    name: str = ""
    description: str = ""

    @property
    @abstractmethod
    def input_schema(self) -> type[InputT]:
        """输入 Pydantic 模型。"""
        ...

    @property
    @abstractmethod
    def output_schema(self) -> type[OutputT]:
        """输出 Pydantic 模型。"""
        ...

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """核心执行逻辑（子类实现）。"""
        ...

    # ---- 标识 ----

    @property
    def key(self) -> str:
        """Tool 唯一标识，默认使用 name，子类可覆写。"""
        return self.name

    # ---- 可覆写的钩子 ----

    async def before_run(self, input_data: InputT) -> None:
        """
        执行前钩子（异步）。
        默认记录日志，子类可覆写添加权限校验、指标埋点等。
        """
        logger.info(f"[{self.name}] 开始执行")

    async def after_run(self, input_data: InputT, output: OutputT, duration_ms: float) -> None:
        """
        成功执行后钩子（异步）。
        默认记录日志，子类可覆写添加成功埋点。
        """
        logger.info(f"[{self.name}] 完成, 耗时 {duration_ms:.0f}ms")

    async def on_error(self, input_data: Optional[InputT], error: Exception) -> None:
        """
        异常钩子（异步）。
        默认记录错误日志，子类可覆写添加异常埋点、告警等。
        """
        logger.error(f"[{self.name}] 异常: {error}")

    async def validate(self, input_data: InputT) -> InputT:
        """
        异步业务校验钩子。
        Pydantic schema 校验已在 input 解析阶段完成，
        此方法做额外的业务规则校验（如数据库查询、LLM 预检）。
        抛出 ValidationError 会被 run() 捕获。
        """
        return input_data

    # ---- 可覆写的配置 ----

    @property
    def timeout_seconds(self) -> float:
        """超时时间，默认 30s。"""
        return 30.0

    @property
    def retry_count(self) -> int:
        """重试次数，默认 0（不重试）。"""
        return 0

    @property
    def retry_delay_seconds(self) -> float:
        """重试间隔（秒），默认 0 表示无等待。LLM 工具建议设为 1.0~3.0 避免限流。"""
        return 0.0

    # ================================================================
    # 父类统一入口（子类禁止覆写）
    # ================================================================

    async def run(self, input_data: Union[InputT, dict[str, Any]]) -> ToolResult[OutputT]:
        """
        统一执行入口。支持传入 Pydantic 模型或 dict。

        流程：
        1. input 解析（dict → InputT）
        2. before_run() 钩子
        3. validate() 异步钩子
        4. execute() 核心逻辑（带超时 + 重试 + 间隔）
        5. after_run() 或 on_error() 钩子
        6. 返回 ToolResult
        """
        start = time.perf_counter()

        try:
            # ---- 0. input 自动解析 ----
            parsed: InputT
            if isinstance(input_data, dict):
                try:
                    parsed = self.input_schema(**input_data)
                except ValidationError as e:
                    duration = (time.perf_counter() - start) * 1000
                    await self._safe_on_error(None, e)
                    return ToolResult.failure(ToolStatus.VALIDATION_ERROR, str(e))
            else:
                parsed = input_data

            # ---- 1. before_run 钩子 ----
            try:
                await self.before_run(parsed)
            except Exception as e:
                logger.warning(f"[{self.name}] before_run 异常: {e}")

            # ---- 2. 异步业务校验钩子 ----
            try:
                validated = await self.validate(parsed)
            except ValidationError as e:
                duration = (time.perf_counter() - start) * 1000
                await self._safe_on_error(parsed, e)
                return ToolResult.failure(ToolStatus.VALIDATION_ERROR, str(e))

            # ---- 3. 执行（带超时 + 重试 + 间隔） ----
            last_error: Optional[Exception] = None
            for attempt in range(self.retry_count + 1):
                try:
                    result = await self._execute_with_timeout(validated)
                    duration = (time.perf_counter() - start) * 1000
                    await self._safe_after_run(validated, result, duration)
                    logger.info(
                        f"[{self.name}] 成功, {duration:.0f}ms"
                        + (f" (attempt {attempt + 1})" if attempt > 0 else "")
                    )
                    return ToolResult.success(result, duration_ms=duration)

                except asyncio.TimeoutError:
                    last_error = TimeoutError(f"[{self.name}] 超时 ({self.timeout_seconds}s)")
                    logger.warning(
                        f"[{self.name}] 超时, attempt {attempt + 1}/{self.retry_count + 1}"
                    )
                except Exception as e:
                    last_error = e
                    logger.error(
                        f"[{self.name}] 异常, attempt {attempt + 1}/{self.retry_count + 1}: {e}"
                    )

                # 重试间隔
                if attempt < self.retry_count and self.retry_delay_seconds > 0:
                    await asyncio.sleep(self.retry_delay_seconds)

            # ---- 全部重试失败 ----
            exc = last_error or RuntimeError("未知错误")
            await self._safe_on_error(parsed, exc)

            status = (
                ToolStatus.TIMEOUT
                if isinstance(exc, TimeoutError)
                else ToolStatus.EXECUTION_ERROR
            )
            return ToolResult.failure(status, str(exc))

        except Exception as e:
            # ---- 全局异常兜底：极端未知崩溃 ----
            duration = (time.perf_counter() - start) * 1000
            logger.critical(f"[{self.name}] 未捕获的严重异常: {e}", exc_info=True)
            await self._safe_on_error(None, e)
            return ToolResult.failure(ToolStatus.EXECUTION_ERROR, str(e))

    async def _execute_with_timeout(self, input_data: InputT) -> OutputT:
        """内部超时控制。"""
        return await asyncio.wait_for(
            self.execute(input_data),
            timeout=self.timeout_seconds,
        )

    async def _safe_after_run(
        self, input_data: InputT, output: OutputT, duration_ms: float
    ) -> None:
        """安全调用 after_run，钩子异常不影响主流程。"""
        try:
            await self.after_run(input_data, output, duration_ms)
        except Exception as e:
            logger.warning(f"[{self.name}] after_run 异常: {e}")

    async def _safe_on_error(
        self, input_data: Optional[InputT], error: Exception
    ) -> None:
        """安全调用 on_error，钩子异常不影响主流程。"""
        try:
            await self.on_error(input_data, error)
        except Exception as e:
            logger.warning(f"[{self.name}] on_error 异常: {e}")
