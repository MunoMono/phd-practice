import { ClickableTile, Grid, InlineNotification, Tag, Tile } from '@carbon/react'
import { useNavigate } from 'react-router-dom'
import { Search, WarningAlt, Checkmark, InProgress, Chip, ArrowRight } from '@carbon/icons-react'
import { useEffect, useMemo, useState } from 'react'
import { getAuthoritySummary } from '../../api/authorities'
import { getDocumentInventorySummary } from '../../api/documents'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import SectionHeading from '../../components/layout/SectionHeading'
import { getClaims } from '../../api/claims'
import { fetchDashboardAnalyticalSurface, fetchDashboardStats } from '../../api/viz'
import { getGraniteModelInfo } from '../../api/granite'
import DashboardAnalyticalSurface from './DashboardAnalyticalSurface'

const formatMetricValue = (value, fallback = 'Not yet recorded') => (value === null || value === undefined ? fallback : value)
const formatCount = (value, fallback = 0) => Number(value ?? fallback).toLocaleString()

const Dashboard = () => {
  const navigate = useNavigate()
  const [graniteInfo, setGraniteInfo] = useState(null)
  const [stats, setStats] = useState(null)
  const [authoritySummary, setAuthoritySummary] = useState(null)
  const [inventorySummary, setInventorySummary] = useState(null)
  const [analyticalSurface, setAnalyticalSurface] = useState(null)
  const [analyticalSurfaceStatus, setAnalyticalSurfaceStatus] = useState('loading')
  const [claims, setClaims] = useState(null)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let isCancelled = false

    const loadDashboard = async () => {
      try {
        const [granitePayload, statsPayload, authorityPayload, inventoryPayload, analyticalResult, claimsPayload] = await Promise.all([
          getGraniteModelInfo().catch(() => null),
          fetchDashboardStats().catch(() => null),
          getAuthoritySummary().catch(() => null),
          getDocumentInventorySummary().catch(() => null),
          fetchDashboardAnalyticalSurface()
            .then((data) => ({ data, status: 'ready' }))
            .catch(() => ({ data: null, status: 'unavailable' })),
          getClaims().catch(() => null),
        ])

        if (isCancelled) {
          return
        }

        setGraniteInfo(granitePayload)
        setStats(statsPayload)
        setAuthoritySummary(authorityPayload)
        setInventorySummary(inventoryPayload)
        setAnalyticalSurface(analyticalResult.data)
        setAnalyticalSurfaceStatus(analyticalResult.status)
        setClaims(claimsPayload?.claims ?? null)
      } catch (error) {
        if (!isCancelled) {
          setLoadError(error.message || 'Failed to load dashboard metrics.')
        }
      }
    }

    loadDashboard()

    return () => {
      isCancelled = true
    }
  }, [])

  const frozenCorpusStatus = useMemo(() => {
    const overview = stats?.overview || {}
    return [
      { label: 'Frozen corpus version', value: analyticalSurface?.corpus_version || 'Loading' },
      {
        label: 'Searchable FTS chunks',
        value: formatCount(analyticalSurface?.composition?.current_chunks ?? overview.totalPages),
        detail: `${formatCount(analyticalSurface?.composition?.controlled_ingestible_sources)} successfully ingested frozen-corpus sources`
      }
    ]
  }, [analyticalSurface, stats])

  const archiveLocalStatus = useMemo(() => {
    const overview = stats?.overview || {}
    const mlProcessing = stats?.mlProcessing || {}
    const corpusCounts = overview.corpusStatus || {}
    const persistedDocumentCount = formatMetricValue(corpusCounts.persistedDocumentCount, 0)
    return [
      {
        label: `Archive-resolved current document records (of ${persistedDocumentCount} local records)`,
        value: formatMetricValue(corpusCounts.archiveResolvedDocumentCount, 0)
      },
      {
        label: `Legacy document records without current archive resolution (of ${persistedDocumentCount} local records)`,
        value: formatMetricValue(corpusCounts.unresolvedLegacyDocumentCount, 0)
      },
      {
        label: 'Documents with stored embeddings',
        value: `${formatMetricValue(mlProcessing.documentsWithEmbeddings, 0)} of ${persistedDocumentCount} local records`,
        detail: 'Inactive for retrieval; PostgreSQL FTS remains active.'
      },
      {
        label: 'ML-authorised archive PDF media',
        // totalPdfs includes retained legacy APR material and is not a frozen-corpus metric.
        value: formatMetricValue(overview.totalPdfAssets, 0),
        detail: 'PID-linked archive metadata'
      }
    ]
  }, [stats])

  const archiveInventoryStatus = useMemo(() => {
    if (!inventorySummary) {
      return []
    }

    return [
      { label: 'Authoritative archive assets', value: inventorySummary.count },
      { label: 'ML-eligible archive assets', value: `${inventorySummary.eligibleUnrestricted + inventorySummary.eligibleRestricted} of ${inventorySummary.count}` },
      { label: 'ML-excluded archive assets', value: `${inventorySummary.excluded} of ${inventorySummary.count}` },
      { label: 'Archive authorities', value: authoritySummary ? `${authoritySummary.totalRecords} records / ${authoritySummary.count} types` : 'Unavailable' },
    ]
  }, [authoritySummary, inventorySummary])

  const recentActivity = stats?.recentActivity?.length
    ? stats.recentActivity.slice(0, 4).map((item) => ({
        label: item.label || item.type || 'Activity',
        detail: `${item.count} recent event${item.count === 1 ? '' : 's'}`
      }))
    : [
        { label: 'Granite retrieval path', detail: 'Healthy on the local Granite model.' },
        { label: 'Frozen corpus', detail: '95 controlled-ingestible source documents and 12,884 current chunks are available for retrieval.' },
        { label: 'Immutable experiments', detail: 'Saved runs preserve retrieval, supplied evidence, model configuration, and export history.' }
      ]

  const limitations = [
    'Retrieval is PostgreSQL full-text search over a versioned, frozen corpus.',
    'Missingness is scoped to the current query, supplied evidence, or ingested corpus.',
    'Authority data provides context; it is not documentary evidence.',
    'Researcher assessment remains human-authored and separate from model output.'
  ]

  return (
    <div className="dashboard">
      <div className="dashboard__hero">
        <div className="dashboard__hero-inner">
          <PageHeader
            title="RCA Department of Design Research archive critical inquiry instrument"
            description="Interrogate sources, trace provenance, surface absences and test interpretations across a computational research corpus."
          />
        </div>
      </div>

      <PageGrid>
        <Column>
          <Tile className="dashboard__granite-hero-content">
            <div className="dashboard__granite-hero-badge">
              <Tag type="blue" size="md">
                <Chip size={20} /> Granite status
              </Tag>
              {graniteInfo && (
                <Tag type={graniteInfo.loaded ? 'green' : 'gray'} size="md">
                  {graniteInfo.loaded ? <Checkmark size={16} /> : <InProgress size={16} />}
                  {graniteInfo.loaded ? ' Active' : ' Standby'}
                </Tag>
              )}
            </div>
            <h2 className="dashboard__granite-hero-title">Research apparatus status</h2>
            <p className="dashboard__granite-hero-description">Live retrieval is available alongside frozen corpus controls, immutable research runs, provenance tracing, and human-authored assessment.</p>
            {graniteInfo && (
              <div className="dashboard__granite-hero-specs">
                <div className="dashboard__granite-hero-spec">
                  <span className="dashboard__granite-hero-spec-label">Model</span>
                  <span className="dashboard__granite-hero-spec-value">{graniteInfo.model_name || 'Unavailable'}</span>
                </div>
                <div className="dashboard__granite-hero-spec">
                  <span className="dashboard__granite-hero-spec-label">Device</span>
                  <span className="dashboard__granite-hero-spec-value">{graniteInfo.device || 'CPU'}</span>
                </div>
                <div className="dashboard__granite-hero-spec">
                  <span className="dashboard__granite-hero-spec-label">Active runtime max tokens</span>
                  <span className="dashboard__granite-hero-spec-value">{graniteInfo.max_tokens ?? 'N/A'}</span>
                </div>
                <div className="dashboard__granite-hero-spec">
                  <span className="dashboard__granite-hero-spec-label">Active runtime temperature</span>
                  <span className="dashboard__granite-hero-spec-value">{graniteInfo.temperature ?? 'N/A'}</span>
                </div>
              </div>
            )}
          </Tile>
        </Column>

        {loadError && (
          <Column>
            <InlineNotification lowContrast kind="warning" title="Dashboard metrics degraded" subtitle={loadError} />
          </Column>
        )}

        <Column>
          <SectionHeading title="Frozen retrieval corpus" />
          <p className="app-copy-tight">Versioned PostgreSQL full-text retrieval evidence, separate from archive inventory and local processing state.</p>
        </Column>

        {frozenCorpusStatus.map((item) => (
          <Column key={item.label} lg={5} xlg={5} max={5} md={4} sm={4}>
            <Tile className="dashboard__info-tile dashboard__metric-tile">
              <h4>{item.label}</h4>
              <p className="dashboard__metric-value">{item.value}</p>
              {item.detail && <p className="app-copy-tight">{item.detail}</p>}
            </Tile>
          </Column>
        ))}

        <Column>
          <SectionHeading title="Archive / local system state" />
          <p className="app-copy-tight">Archive metadata and inactive embedding state are not measures of frozen-corpus retrieval coverage.</p>
        </Column>

        {archiveLocalStatus.map((item) => (
          <Column key={item.label} lg={5} xlg={5} max={5} md={4} sm={4}>
            <Tile className="dashboard__info-tile dashboard__metric-tile">
              <h4>{item.label}</h4>
              <p className="dashboard__metric-value">{item.value}</p>
              {item.detail && <p className="app-copy-tight">{item.detail}</p>}
            </Tile>
          </Column>
        ))}

        {archiveInventoryStatus.length > 0 && (
          <>
            <Column>
              <SectionHeading title="Archive inventory" />
              <p className="app-copy-tight">Live archive-backed source inventory exposed in Sources, separate from the frozen retrieval corpus.</p>
            </Column>

            {archiveInventoryStatus.map((item) => (
              <Column key={item.label} lg={5} xlg={5} max={5} md={4} sm={4}>
                <Tile className="dashboard__info-tile dashboard__metric-tile">
                  <h4>{item.label}</h4>
                  <p className="dashboard__metric-value">{item.value}</p>
                </Tile>
              </Column>
            ))}
          </>
        )}

        <Column>
          <SectionHeading title="Analytical surface" />
        </Column>

        <Column>
          <DashboardAnalyticalSurface
            data={analyticalSurface}
            claims={claims}
            claimsAvailable={claims !== null}
            status={analyticalSurfaceStatus}
          />
        </Column>

        <Column>
          <SectionHeading title="Supporting views" />
        </Column>

        <Column>
          <Grid className="dashboard__supporting-grid">
            <Column lg={5} xlg={5} max={5} md={4} sm={4}>
              <ClickableTile onClick={() => navigate('/sources')} className="dashboard__tile dashboard__supporting-tile">
                <div className="dashboard__tile-icon">
                  <Search size={32} />
                </div>
                <h3>Sources</h3>
                <p>Inspect corpus records, policy, page scope, and provenance before interrogation.</p>
              </ClickableTile>
            </Column>

            <Column lg={5} xlg={5} max={5} md={4} sm={4}>
              <ClickableTile onClick={() => navigate('/research-runs')} className="dashboard__tile dashboard__supporting-tile">
                <div className="dashboard__tile-icon">
                  <ArrowRight size={32} />
                </div>
                <h3>Research runs</h3>
                <p>Review immutable retrieval and inference experiments with supplied evidence and exportable records.</p>
              </ClickableTile>
            </Column>

            <Column lg={5} xlg={5} max={5} md={4} sm={4}>
              <ClickableTile onClick={() => navigate('/provenance')} className="dashboard__tile dashboard__supporting-tile">
                <div className="dashboard__tile-icon">
                  <WarningAlt size={32} />
                </div>
                <h3>Provenance</h3>
                <p>Trace query, evidence, authority, and export histories across the research apparatus.</p>
              </ClickableTile>
            </Column>

            <Column lg={5} xlg={5} max={5} md={4} sm={4}>
              <ClickableTile onClick={() => navigate('/claims-evidence')} className="dashboard__tile dashboard__supporting-tile">
                <div className="dashboard__tile-icon">
                  <Checkmark size={32} />
                </div>
                <h3>Claims and evidence</h3>
                <p>Review claims against supporting archival evidence and their researcher-held interpretive status.</p>
              </ClickableTile>
            </Column>
          </Grid>
        </Column>

        <Column lg={5} md={8} sm={4}>
          <Tile className="dashboard__info-tile">
            <SectionHeading title="Recent research activity" />
            <div className="app-card-grid app-card-grid--dense">
              {recentActivity.map((item) => (
                <div key={item.label}>
                  <strong>{item.label}</strong>
                  <p className="app-copy-tight">{item.detail}</p>
                </div>
              ))}
            </div>
          </Tile>
        </Column>

        <Column lg={5} md={8} sm={4}>
          <Tile className="dashboard__info-tile">
            <SectionHeading title="Methodological boundaries" />
            <div className="app-card-grid app-card-grid--dense">
              {limitations.map((item) => (
                <p key={item} className="app-copy-reset">{item}</p>
              ))}
            </div>
          </Tile>
        </Column>

      </PageGrid>
    </div>
  )
}

export default Dashboard
