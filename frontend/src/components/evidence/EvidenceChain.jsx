import { InlineNotification } from '@carbon/react'
import EvidenceSourceCard from './EvidenceSourceCard'

const EvidenceChain = ({
  sources,
  showEmptyState = false,
  onCopyCitation,
  onOpenCorpus,
  onShowAnalytics,
  onToggleProvenance
}) => {
  if (!sources || sources.length === 0) {
    if (!showEmptyState) {
      return null
    }

    return (
      <InlineNotification
        lowContrast
        kind="warning"
        title="No source chunks returned"
        subtitle="The current endpoint returned an answer, but no supporting source chunks were included in the response."
      />
    )
  }

  return (
    <div className="evidence-chain">
      {sources.map((source, index) => (
        <EvidenceSourceCard
          key={source.chunkId || `source-${index}`}
          source={source}
          index={index}
          onCopyCitation={() => onCopyCitation(source)}
          onOpenCorpus={() => onOpenCorpus(source)}
          onShowAnalytics={() => onShowAnalytics(source)}
          onToggleProvenance={() => onToggleProvenance(source)}
        />
      ))}
    </div>
  )
}

export default EvidenceChain