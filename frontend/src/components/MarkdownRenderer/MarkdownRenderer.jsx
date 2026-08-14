import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './../../styles/components/Markdown.scss'

const MarkdownRenderer = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ children }) => (
            <div className="markdown-content__table-scroll">
              <table>{children}</table>
            </div>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default MarkdownRenderer
