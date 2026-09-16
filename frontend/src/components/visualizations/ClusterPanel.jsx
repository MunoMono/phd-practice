import { Button, Tag, Tile } from '@carbon/react'

const ClusterPanel = ({ clusters, selectedCluster, onSelectCluster, onCopyClusterMemo }) => {
  return (
    <Tile className="cluster-panel">
      <div className="cluster-panel__header">
        <div>
          <h3>Cluster panel</h3>
          <p>Inspect thematic groupings, year ranges, and representative PIDs from the projection.</p>
        </div>
        {selectedCluster && <Button kind="ghost" size="sm" onClick={onCopyClusterMemo}>Copy cluster interpretation note</Button>}
      </div>

      {clusters.length === 0 ? (
        <p>No cluster metadata is available from the current endpoint.</p>
      ) : (
        <div className="cluster-panel__list">
          {clusters.map((cluster) => (
            <button
              key={cluster.id}
              type="button"
              className={`cluster-panel__item ${selectedCluster?.id === cluster.id ? 'cluster-panel__item--active' : ''}`}
              onClick={() => onSelectCluster(selectedCluster?.id === cluster.id ? null : cluster)}
            >
              <div className="cluster-panel__item-head">
                <strong>{cluster.label}</strong>
                <Tag type="purple">{cluster.size}</Tag>
              </div>
              <div>Top terms: {cluster.topTerms?.join(', ') || 'Unavailable'}</div>
              <div>Year range: {cluster.yearRange?.join(' - ') || 'Unavailable'}</div>
              <div>Representative PIDs: {cluster.representativePids?.join(', ') || 'Unavailable'}</div>
            </button>
          ))}
        </div>
      )}
    </Tile>
  )
}

export default ClusterPanel