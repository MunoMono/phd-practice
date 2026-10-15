import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { scholarlyRemarkPlugin } from '../../utils/scholarlyPresentation'

const ScholarlyAnswer = ({ presentation }) => (
  <ReactMarkdown remarkPlugins={[remarkGfm, scholarlyRemarkPlugin(presentation)]}>
    {presentation.text}
  </ReactMarkdown>
)

export default ScholarlyAnswer
