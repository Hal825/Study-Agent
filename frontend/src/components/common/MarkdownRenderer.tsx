import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownRendererProps {
  content: string
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="prose prose-gray max-w-none animate-fade-in">
      <style>{`
        .markdown-body h1 { font-size: 1.75rem; font-weight: 700; margin-top: 2rem; margin-bottom: 1rem; color: #111827; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }
        .markdown-body h2 { font-size: 1.4rem; font-weight: 600; margin-top: 1.75rem; margin-bottom: 0.75rem; color: #1f2937; }
        .markdown-body h3 { font-size: 1.15rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem; color: #374151; }
        .markdown-body p { margin-bottom: 1rem; line-height: 1.8; color: #4b5563; }
        .markdown-body ul, .markdown-body ol { margin-bottom: 1rem; padding-left: 1.5rem; }
        .markdown-body li { margin-bottom: 0.25rem; line-height: 1.7; color: #4b5563; }
        .markdown-body strong { color: #111827; font-weight: 600; }
        .markdown-body blockquote { border-left: 4px solid #3b82f6; padding: 0.75rem 1rem; margin: 1rem 0; background: #f0f9ff; border-radius: 0 0.5rem 0.5rem 0; }
        .markdown-body blockquote p { margin-bottom: 0; color: #1e40af; }
        .markdown-body code { background: #f3f4f6; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.875rem; color: #dc2626; }
        .markdown-body pre { background: #1f2937; padding: 1rem 1.25rem; border-radius: 0.75rem; overflow-x: auto; margin: 1rem 0; }
        .markdown-body pre code { background: none; padding: 0; color: #e5e7eb; font-size: 0.875rem; }
        .markdown-body table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
        .markdown-body th { background: #f9fafb; padding: 0.75rem 1rem; text-align: left; font-weight: 600; color: #374151; border-bottom: 2px solid #e5e7eb; font-size: 0.875rem; }
        .markdown-body td { padding: 0.75rem 1rem; border-bottom: 1px solid #f3f4f6; color: #4b5563; font-size: 0.875rem; }
        .markdown-body hr { border: none; border-top: 2px solid #e5e7eb; margin: 2rem 0; }
        .markdown-body a { color: #2563eb; text-decoration: underline; }
      `}</style>
      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}
