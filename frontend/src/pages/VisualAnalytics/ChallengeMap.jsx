import { Button, InlineNotification, NumberInput, Tag, Tile } from '@carbon/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { challengeUmapProjection } from '../../api/viz'
import PanelHeader from '../../components/layout/PanelHeader'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import UmapPointDetail from '../../components/visualizations/UmapPointDetail'
import UmapEvidenceTable from '../../components/visualizations/UmapEvidenceTable'
import UmapProjection from '../../components/visualizations/UmapProjection'
import { normalizeUmapProjection } from '../../utils/normalizers'

const ChallengeMap = () => {
  const navigate = useNavigate()
  const [parameters, setParameters] = useState({ random_seed: 42, n_neighbors: 15, min_dist: 0.1, sample_size: 500 })
  const [projection, setProjection] = useState({ points: [], metadata: {} })
  const [selectedPoint, setSelectedPoint] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const updateParameter = (field, value) => setParameters((current) => ({ ...current, [field]: Number(value) }))

  const runChallenge = async () => {
    setLoading(true)
    setError('')
    try {
      setProjection(normalizeUmapProjection(await challengeUmapProjection(parameters)))
      setSelectedPoint(null)
    } catch (requestError) {
      setError(requestError.message || 'The temporary UMAP projection could not be generated.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <PageGrid className="challenge-map-page">
      <Column>
        <PageHeader title="Challenge this map" description="Test whether visually persuasive structures remain stable when the projection parameters change." actions={<Tag type="purple">Methodological scrutiny</Tag>} />
      </Column>
      <Column>
        <InlineNotification lowContrast kind="warning" title="Temporary projection, not a finding" subtitle="This view recalculates a read-only sample from the completed embedding set. It does not overwrite the Semantic Atlas or prove that an apparent relationship is historical." />
      </Column>
      {error && <Column><InlineNotification lowContrast kind="error" title="Challenge projection unavailable" subtitle={error} /></Column>}
      <Column>
        <Tile className="challenge-map-page__controls">
          <PanelHeader title="Projection variant" description="Change one or more parameters, then compare the resulting evidence surface with the persisted Atlas." />
          <div className="challenge-map-page__grid">
            <NumberInput id="challenge-seed" label="Random seed" value={parameters.random_seed} min={0} max={9999} onChange={(event) => updateParameter('random_seed', event.target.value)} />
            <NumberInput id="challenge-neighbours" label="UMAP neighbours" value={parameters.n_neighbors} min={2} max={100} onChange={(event) => updateParameter('n_neighbors', event.target.value)} />
            <NumberInput id="challenge-distance" label="Minimum distance" value={parameters.min_dist} min={0} max={0.99} step={0.01} onChange={(event) => updateParameter('min_dist', event.target.value)} />
            <NumberInput id="challenge-sample" label="Sample size" value={parameters.sample_size} min={50} max={1000} step={50} onChange={(event) => updateParameter('sample_size', event.target.value)} />
          </div>
          <Button onClick={runChallenge} disabled={loading}>{loading ? 'Generating challenge projection...' : 'Generate challenge projection'}</Button>
        </Tile>
      </Column>
      {projection.points.length === 0 && !loading && <Column><InlineNotification lowContrast kind="info" title="No variant generated" subtitle="Generate a temporary projection to inspect how this evidence surface responds to parameter change." /></Column>}
      {projection.points.length > 0 && <>
        <Column>
          <Tile className="challenge-map-page__apparatus"><PanelHeader title="Variant apparatus" description="Record these settings alongside any observation made from this temporary representation." /><div className="challenge-map-page__grid"><p><strong>Method:</strong> {projection.metadata.projectionMethod}</p><p><strong>Seed:</strong> {projection.metadata.randomSeed}</p><p><strong>Neighbours:</strong> {projection.metadata.nNeighbors}</p><p><strong>Minimum distance:</strong> {projection.metadata.minDist}</p><p><strong>Sample:</strong> {projection.metadata.sampleSize}</p><p><strong>Embedding set:</strong> {projection.metadata.embeddingSetId}</p></div></Tile>
        </Column>
        <Column lg={10} md={8} sm={4}><Tile className="challenge-map-page__projection"><PanelHeader title="Temporary UMAP variant" description="Select a point to inspect the same archival evidence behind this alternative representation." actions={<Tag type="gray">Points: {projection.points.length}</Tag>} /><UmapProjection points={projection.points} loading={loading} errorState={error} selectedPoint={selectedPoint} highlightedTrace={null} colorBy="cluster" onSelectPoint={setSelectedPoint} /></Tile></Column>
        <Column lg={6} md={8} sm={4}><UmapPointDetail point={selectedPoint} onOpenCorpus={() => navigate(`/sources?documentId=${encodeURIComponent(selectedPoint?.documentId || '')}`)} onTraceEvidence={() => navigate(`/source-interrogation?chunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onOpenAbsences={() => navigate(`/absences?sourceDocumentId=${encodeURIComponent(selectedPoint?.documentId || '')}&sourceChunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onOpenCrossReadings={() => navigate(`/cross-readings?sourceDocumentId=${encodeURIComponent(selectedPoint?.documentId || '')}&sourceChunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onCopyPid={() => navigator.clipboard?.writeText(selectedPoint?.pid || '')} onCopyExcerpt={() => navigator.clipboard?.writeText(selectedPoint?.excerpt || '')} onAddToMemo={() => {}} /></Column>
        <Column><Tile className="challenge-map-page__projection"><PanelHeader title="Variant archival evidence" description="Sort this temporary projection's sampled evidence and select a row to inspect its source." /><UmapEvidenceTable points={projection.points} onInspect={setSelectedPoint} /></Tile></Column>
      </>}
    </PageGrid>
  )
}

export default ChallengeMap