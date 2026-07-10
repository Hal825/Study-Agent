"""
Prompt 构造器 —— 纯字符串操作，带变量校验。
"""

import re


class PromptBuilder:
    """
    Prompt 构造器。

    职责：将模板中的 {variable} 占位符替换为实际值。
    不包含任何业务逻辑，不依赖任何其他层。
    """

    @staticmethod
    def build(template: str, **variables: str) -> str:
        """
        填充模板变量。

        Args:
            template: 包含 {var} 占位符的模板文本
            **variables: 变量名 → 值的映射

        Returns:
            填充后的文本

        Raises:
            ValueError: 模板中存在未传入的占位符变量
            KeyError: 传入的变量值不是字符串类型

        示例:
            >>> PromptBuilder.build("你好 {name}", name="世界")
            '你好 世界'
            >>> PromptBuilder.build("你好 {name}")  # 缺失变量
            ValueError: 模板缺失变量: ['name']
        """
        # 提取模板中所有 {var} 占位符
        placeholders = re.findall(r"\{(\w+)\}", template)
        unique_placeholders = list(dict.fromkeys(placeholders))  # 去重保序

        # 校验：模板中所有占位符都已传入
        missing = [p for p in unique_placeholders if p not in variables]
        if missing:
            raise ValueError(
                f"模板缺失变量: {missing}，"
                f"已传入: {list(variables.keys())}，"
                f"模板占位符: {unique_placeholders}"
            )

        return template.format(**variables)

    @staticmethod
    def extract_placeholders(template: str) -> list[str]:
        """
        提取模板中所有占位符变量名（调试辅助）。

        Returns:
            去重后的变量名列表
        """
        return list(dict.fromkeys(re.findall(r"\{(\w+)\}", template)))
