import ReactMarkdown from 'react-markdown';

interface MarkdownRendererProps {
  content: string;
}

/**
 * 轻量 Markdown 渲染组件
 *
 * 后端 answer_organize_tool 输出的内容使用有限的 Markdown 子集：
 *   - # 一级标题
 *   - ## 二级标题
 *   - - 无序列表
 *   - 数字序号 有序列表
 *   - 纯文本段落、换行
 *
 * 本组件使用 react-markdown 将这些内容渲染为带样式的 HTML，
 * 使前端消息气泡中的内容展示整齐、可读。
 */
export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="markdown-body">
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  );
}
