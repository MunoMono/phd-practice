import { Button, InlineNotification, NumberInput, Tag, TextArea, TextInput, Tile } from '@carbon/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { challengeUmapProjection, getSemanticNeighbourhood, getUmapChallengeRun, getUmapProjection } from '../../api/viz'
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
  const [researcherNote, setResearcherNote] = useState('')
  const [challengeRunId, setChallengeRunId] = useState('')
  const [projection, setProjection] = useState({ points: [], metadata: {} })
  const [baselinePoints, setBaselinePoints] = useState([])
  const [originalSpaceNeighbours, setOriginalSpaceNeighbours] = useState([])
  const [neighbourhoodError, setNeighbourhoodError] = useState('')
  const [selectedPoint, setSelectedPoint] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const updateParameter = (field, value) => setParameters((current) => ({ ...current, [field]: Number(value) }))

  const loadBaseline = async () => {
    try {
      const baselineProjection = await getUmapProjection({ point_type: 'chunks', limit: 1000 })
      setBaselinePoints(baselineProjection.points || [])
    } catch {
      setBaselinePoints([])
    }
  }

  const runChallenge = async () => {
    setLoading(true)
    setError('')
    try {
      const challengeProjection = normalizeUmapProjection(await challengeUmapProjection({ ...parameters, researcher_note: researcherNote.trim() || null }))
      setProjection(challengeProjection)
      setChallengeRunId(challengeProjection.metadata.challengeRunId || '')
      setSelectedPoint(null)
      setOriginalSpaceNeighbours([])
      setNeighbourhoodError('')
      await loadBaseline()
    } catch (requestError) {
      setError(requestError.message || 'The temporary UMAP projection could not be generated.')
    } finally {
      setLoading(false)
    }
  }

  const loadChallengeRun = async () => {
    if (!challengeRunId.trim()) return
    setLoading(true)
    setError('')
    try {
      const challengeRun = await getUmapChallengeRun(challengeRunId.trim())
      if (!challengeRun.result?.points?.length) throw new Error('The saved challenge run does not retain a projection result.')
      setProjection(normalizeUmapProjection(challengeRun.result))
      setResearcherNote(challengeRun.researcher_note || '')
      setSelectedPoint(null)
      setOriginalSpaceNeighbours([])
      setNeighbourhoodError('')
      await loadBaseline()
    } catch (requestError) {
      setError(requestError.message || 'The saved challenge projection could not be loaded.')
    } finally {
      setLoading(false)
    }
  }

  const exportChallengeRecord = () => {
    const payload = JSON.stringify({
      workflow: 'UMAP sensitivity challenge',
      researcher_note: researcherNote.trim() || null,
      projection,
    }, null, 2)
    const url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${projection.metadata.challengeRunId || 'umap-challenge'}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const loadOriginalSpaceNeighbours = async () => {
    if (!selectedPoint?.chunkId) return
    setNeighbourhoodError('')
    try {
      const result = await getSemanticNeighbourhood({ focal_chunk_id: selectedPoint.chunkId, size: 10 })
      setOriginalSpaceNeighbours(result.neighbours || [])
    } catch (requestError) {
      setNeighbourhoodError(requestError.message || 'Original-space neighbourhood retrieval is unavailable for this source.')
    }
  }

  const baselinePoint = selectedPoint ? baselinePoints.find((point) => point.id === selectedPoint.id || point.chunkId === selectedPoint.chunkId) : null

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
          <TextArea id="challenge-note" labelText="Researcher note" value={researcherNote} onChange={(event) => setResearcherNote(event.target.value)} rows={3} />
          <Button onClick={runChallenge} disabled={loading}>{loading ? 'Generating challenge projection...' : 'Generate challenge projection'}</Button>
          <TextInput id="challenge-run-id" labelText="Saved challenge run ID" value={challengeRunId} onChange={(event) => setChallengeRunId(event.target.value)} />
          <Button kind="secondary" onClick={loadChallengeRun} disabled={loading || !challengeRunId.trim()}>Load saved challenge projection</Button>
        </Tile>
      </Column>
      {projection.points.length === 0 && !loading && <Column><InlineNotification lowContrast kind="info" title="No variant generated" subtitle="Generate a temporary projection to inspect how this evidence surface responds to parameter change." /></Column>}
      {projection.points.length > 0 && <>
        <Column>
          <Tile className="challenge-map-page__apparatus"><PanelHeader title="Variant apparatus" description="This separately identified sensitivity record never replaces the persisted Atlas." actions={<Button size="sm" kind="ghost" onClick={exportChallengeRecord}>Export record</Button>} /><div className="challenge-map-page__grid"><p><strong>Challenge run:</strong> {projection.metadata.challengeRunId}</p><p><strong>Source projection:</strong> {projection.metadata.sourceProjectionId}</p><p><strong>Method:</strong> {projection.metadata.projectionMethod}</p><p><strong>Library:</strong> {projection.metadata.algorithmLibrary}</p><p><strong>Metric:</strong> {projection.metadata.metric}</p><p><strong>Seed:</strong> {projection.metadata.randomSeed}</p><p><strong>Neighbours:</strong> {projection.metadata.nNeighbors}</p><p><strong>Minimum distance:</strong> {projection.metadata.minDist}</p><p><strong>Sample:</strong> {projection.metadata.sampleSize}</p><p><strong>Sample order:</strong> {projection.metadata.sampleOrder}</p><p><strong>Embedding set:</strong> {projection.metadata.embeddingSetId}</p></div></Tile>
        </Column>
        <Column lg={10} md={8} sm={4}><Tile className="challenge-map-page__projection"><PanelHeader title="Temporary UMAP variant" description="Select a point to inspect the same archival evidence behind this alternative representation." actions={<Tag type="gray">Points: {projection.points.length}</Tag>} /><UmapProjection points={projection.points} loading={loading} errorState={error} selectedPoint={selectedPoint} highlightedTrace={null} colorBy="cluster" onSelectPoint={setSelectedPoint} /></Tile></Column>
        <Column lg={6} md={8} sm={4}><UmapPointDetail point={selectedPoint} onOpenCorpus={() => navigate(`/sources?documentId=${encodeURIComponent(selectedPoint?.documentId || '')}`)} onTraceEvidence={() => navigate(`/source-interrogation?chunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onOpenAbsences={() => navigate(`/absences?sourceDocumentId=${encodeURIComponent(selectedPoint?.documentId || '')}&sourceChunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onOpenCrossReadings={() => navigate(`/cross-readings?sourceDocumentId=${encodeURIComponent(selectedPoint?.documentId || '')}&sourceChunkId=${encodeURIComponent(selectedPoint?.chunkId || '')}`)} onCopyPid={() => navigator.clipboard?.writeText(selectedPoint?.pid || '')} onCopyExcerpt={() => navigator.clipboard?.writeText(selectedPoint?.excerpt || '')} onAddToMemo={() => {}} /></Column>
        <Column lg={6} md={8} sm={4}><Tile className="challenge-map-page__apparatus"><PanelHeader title="Primary projection correspondence" description="The same source-linked point in the stored baseline and this temporary variant. Coordinate differences are not a stability verdict." />{selectedPoint ? baselinePoint ? <dl><dt>Source chunk</dt><dd>{selectedPoint.chunkId || selectedPoint.id}</dd><dt>Stored baseline</dt><dd>{baselinePoint.x.toFixed(3)}, {baselinePoint.y.toFixed(3)}</dd><dt>Temporary variant</dt><dd>{selectedPoint.x.toFixed(3)}, {selectedPoint.y.toFixed(3)}</dd></dl> : <p>The selected challenge point has no returned stored-baseline correspondence in this bounded comparison surface.</p> : <p>Select a challenge point to compare its source-linked coordinates.</p>}<Button size="sm" kind="ghost" onClick={loadOriginalSpaceNeighbours} disabled={!selectedPoint?.chunkId}>Inspect original-space neighbours</Button>{neighbourhoodError && <InlineNotification lowContrast kind="error" title="Original-space neighbourhood unavailable" subtitle={neighbourhoodError} />}{originalSpaceNeighbours.length > 0 && <><h3>Original-space neighbours</h3><p>Top 10 original embedding-space neighbours. This display `k` is retrieval-only and does not change either projection.</p><ol>{originalSpaceNeighbours.map((neighbour) => <li key={neighbour.chunk_id || neighbour.id}>{neighbour.rank}: {neighbour.title || neighbour.chunk_id || neighbour.id} ({neighbour.similarity ?? neighbour.distance ?? 'metric unavailable'})</li>)}</ol></>}</Tile></Column>
        <Column><Tile className="challenge-map-page__projection"><PanelHeader title="Variant archival evidence" description="Sort this temporary projection's sampled evidence and select a row to inspect its source." /><UmapEvidenceTable points={projection.points} onInspect={setSelectedPoint} /></Tile></Column>
      </>}
    </PageGrid>
  )
}

export default ChallengeMap