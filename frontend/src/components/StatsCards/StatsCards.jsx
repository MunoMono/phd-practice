import { useState, useEffect } from 'react'
import { Grid, Column, Tile, SkeletonText, ProgressBar, Tag } from '@carbon/react'
import { DataBase, CloudApp, Cube, Chemistry } from '@carbon/icons-react'
import '../../styles/components/StatsCards.scss'

const StatsCards = () => {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [recentDocs, setRecentDocs] = useState([])
  const [pidAuthorities, setPidAuthorities] = useState([])

  useEffect(() => {
    fetchStats()
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchStats = async () => {
    try {
      // GraphQL query for PID-gated corpus metrics and recent documents
      const query = `
        query {
          systemMetrics {
            localDb {
              total
              tableCounts {
                documentEmbeddings
                researchSessions
                experiments
                digitalAssets
                documents
                trainingRuns
                corpusSnapshots
              }
            }
            s3Storage {
              totalAssets
              totalSizeMb
              configured
              images
              pdfs
              tiffs
            }
            totalItems
            pidCount
            pidAuthorities {
              pid
              title
              documentCount
            }
          }
          recentDocuments(days: 7) {
            pid
            title
            createdAt
          }
        }
      `
      
      // Use environment-aware URL - in production, use /api/graphql, in dev use localhost
      const graphqlUrl = import.meta.env.PROD 
        ? '/api/graphql' 
        : 'http://localhost:8000/graphql'
      
      const response = await fetch(graphqlUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query })
      })
      
      if (!response.ok) throw new Error('Failed to fetch stats')
      
      const result = await response.json()
      if (result.errors) {
        throw new Error(result.errors[0].message)
      }
      
      const metrics = result.data.systemMetrics
      const recent = result.data.recentDocuments || []
      
      // Set recent documents
      setRecentDocs(recent)
      
      // Set PID authorities
      setPidAuthorities(metrics.pidAuthorities || [])
      
      // Transform to match existing component structure
      setStats({
        total_db_records: metrics.localDb.total,
        local_db_records: metrics.localDb.total,
        local_table_counts: {
          document_embeddings: metrics.localDb.tableCounts.documentEmbeddings,
          research_sessions: metrics.localDb.tableCounts.researchSessions,
          experiments: metrics.localDb.tableCounts.experiments,
          documents: metrics.localDb.tableCounts.documents || 0,
          training_runs: metrics.localDb.tableCounts.trainingRuns || 0,
          corpus_snapshots: metrics.localDb.tableCounts.corpusSnapshots || 0
        },
        total_s3_assets: metrics.localDb.tableCounts.digitalAssets,
        total_s3_size_mb: 0,
        s3_configured: true,
        s3_images: metrics.s3Storage.images,
        s3_pdfs: metrics.s3Storage.pdfs,
        s3_tiffs: metrics.s3Storage.tiffs || 0,
        total_items: metrics.totalItems,
        pid_count: metrics.pidCount || 3
      })
      setError(null)
    } catch (err) {
      console.error('Error fetching stats:', err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === undefined || num === null) return '0'
    return num.toLocaleString()
  }

  if (loading) {
    return (
      <Grid condensed className="stats-cards">
        <Column lg={5} md={4} sm={4}>
          <Tile className="stats-card stats-card--loading">
            <SkeletonText />
          </Tile>
        </Column>
        <Column lg={5} md={4} sm={4}>
          <Tile className="stats-card stats-card--loading">
            <SkeletonText />
          </Tile>
        </Column>
        <Column lg={6} md={4} sm={4}>
          <Tile className="stats-card stats-card--loading">
            <SkeletonText />
          </Tile>
        </Column>
      </Grid>
    )
  }

  if (error) {
    return (
      <Grid condensed className="stats-cards">
        <Column lg={16} md={8} sm={4}>
          <Tile className="stats-card stats-card--error">
            <p>Unable to load statistics: {error}</p>
          </Tile>
        </Column>
      </Grid>
    )
  }

  return (
    <Grid condensed className="stats-cards">
      <Column lg={4} md={2} sm={4}>
        <Tile className="stats-card stats-card--database">
          <div className="stats-card__icon">
            <DataBase size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.pid_count)}
            </div>
            <div className="stats-card__label">PID-Validated Authorities</div>
            <div className="stats-card__progress">
              <ProgressBar 
                label="Year 1 Target" 
                value={stats?.pid_count || 0} 
                max={50} 
               pidAuthorities.length > 0 && (
                <div className="stats-card__recent" style={{ marginTop: '8px', fontSize: '0.75rem', color: 'var(--cds-text-secondary)' }}>
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>PID authorities:</div>
                  {pidAuthorities.map((auth, idx) => (
                    <div key={idx} style={{ marginLeft: '8px', marginBottom: '2px', fontFamily: 'monospace' }}>
                      • {auth.title} | {auth.pid}
                    </div>
                  ))}
                </div>
              )}
              {recentDocs.length > 0 && pidAuthorities.length ===
              />
              <div className="stats-card__progress-label">
                {stats?.pid_count || 0}/50 authorities curated
              </div>
            </div>
            <div className="stats-card__breakdown">
              <Tag type="blue" size="sm">{formatNumber(stats?.local_table_counts?.documents || 0)} docs ingested</Tag>
              {recentDocs.length > 0 && (
                <div className="stats-card__recent" style={{ marginTop: '8px', fontSize: '0.75rem', color: 'var(--cds-text-secondary)' }}>
                  <div style={{ fontWeight: '600', marginBottom: '4px' }}>Recent items (past week):</div>
                  {recentDocs.map((doc, idx) => (
                    <div key={idx} style={{ marginLeft: '8px', marginBottom: '2px' }}>
                      • {doc.title} <span style={{ opacity: 0.6 }}>({doc.pid})</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Tile>
      </Column>

      <Column lg={4} md={2} sm={4}>
        <Tile className="stats-card stats-card--storage">
          <div className="stats-card__icon">
            <CloudApp size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.local_table_counts?.document_embeddings || 0)}
            </div>
            <div className="stats-card__label">Document Chunks</div>
            <div className="stats-card__breakdown">
              <Tag type="green" size="sm">384-dim BERT</Tag>
              <div className="stats-card__meta">
                {formatNumber(stats?.s3_pdfs || 0)} PDFs · {formatNumber(stats?.s3_tiffs || 0)} TIFFs
              </div>
            </div>
          </div>
        </Tile>
      </Column>

      <Column lg={4} md={2} sm={4}>
        <Tile className="stats-card stats-card--total">
          <div className="stats-card__icon">
            <Cube size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.local_table_counts?.corpus_snapshots || 0)}
            </div>
            <div className="stats-card__label">Corpus Snapshots</div>
            <div className="stats-card__breakdown">
              <Tag type="purple" size="sm">SHA-256 versioned</Tag>
              <div className="stats-card__meta">
                {formatNumber(stats?.local_table_counts?.training_runs || 0)} training runs logged
              </div>
            </div>
          </div>
        </Tile>
      </Column>

      <Column lg={4} md={2} sm={4}>
        <Tile className="stats-card stats-card--experiments">
          <div className="stats-card__icon">
            <Chemistry size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.local_table_counts?.experiments || 0)}
            </div>
            <div className="stats-card__label">Experiments</div>
            <div className="stats-card__breakdown">
              <Tag type="warm-gray" size="sm">Granite fine-tuning</Tag>
              <div className="stats-card__meta">
                {formatNumber(stats?.local_table_counts?.research_sessions || 0)} inference sessions
              </div>
            </div>
          </div>
        </Tile>
      </Column>
    </Grid>
  )
}

export default StatsCards
