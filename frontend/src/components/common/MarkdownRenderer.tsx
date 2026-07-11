import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface MarkdownRendererProps {
  content: string
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <div className="animate-fade-in">
      <style>{`
        .md-body {
          color: #2D2A26;
          line-height: 1.85;
          font-size: 0.9375rem;
        }
        .md-body h1 {
          font-family: Georgia, 'Times New Roman', serif;
          font-size: 1.5rem;
          font-weight: 700;
          margin-top: 2.5rem;
          margin-bottom: 1rem;
          color: #2D2A26;
          letter-spacing: -0.01em;
        }
        .md-body h1:first-child { margin-top: 0; }
        .md-body h2 {
          font-family: Georgia, 'Times New Roman', serif;
          font-size: 1.2rem;
          font-weight: 600;
          margin-top: 2rem;
          margin-bottom: 0.75rem;
          color: #4F4942;
        }
        .md-body h3 {
          font-size: 1.05rem;
          font-weight: 600;
          margin-top: 1.5rem;
          margin-bottom: 0.5rem;
          color: #655D54;
        }
        .md-body p {
          margin-bottom: 1rem;
          color: #6B6762;
        }
        .md-body ul, .md-body ol {
          margin-bottom: 1rem;
          padding-left: 1.5rem;
        }
        .md-body li {
          margin-bottom: 0.25rem;
          color: #6B6762;
        }
        .md-body strong {
          color: #2D2A26;
          font-weight: 600;
        }
        .md-body blockquote {
          border-left: 3px solid #C8984E;
          padding: 0.75rem 1rem;
          margin: 1.25rem 0;
          background: #FDF9F3;
          border-radius: 0 0.5rem 0.5rem 0;
        }
        .md-body blockquote p {
          margin-bottom: 0;
          color: #87602E;
        }
        .md-body code {
          background: #F2F0EC;
          padding: 0.15rem 0.4rem;
          border-radius: 0.3rem;
          font-size: 0.85rem;
          color: #655D54;
          font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace;
        }
        .md-body pre {
          background: #2D2A26;
          padding: 1rem 1.25rem;
          border-radius: 0.75rem;
          overflow-x: auto;
          margin: 1rem 0;
        }
        .md-body pre code {
          background: none;
          padding: 0;
          color: #EDEAE5;
          font-size: 0.8rem;
        }
        .md-body table {
          width: 100%;
          border-collapse: collapse;
          margin: 1rem 0;
          font-size: 0.875rem;
        }
        .md-body th {
          background: #FAF9F6;
          padding: 0.75rem 1rem;
          text-align: left;
          font-weight: 600;
          color: #2D2A26;
          border-bottom: 1.5px solid #EDEAE5;
        }
        .md-body td {
          padding: 0.75rem 1rem;
          border-bottom: 1px solid #F3F1ED;
          color: #6B6762;
        }
        .md-body hr {
          border: none;
          border-top: 1px solid #EDEAE5;
          margin: 2rem 0;
        }
        .md-body a {
          color: #655D54;
          text-decoration: underline;
          text-underline-offset: 2px;
        }
      `}</style>
      <div className="md-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    </div>
  )
}
