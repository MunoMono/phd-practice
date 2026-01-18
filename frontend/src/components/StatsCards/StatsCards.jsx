import { useState, useEffect } from 'react'
import { Grid, Column, Tile, SkeletonText } from '@carbon/react'
import { DataBase, CloudApp, Cube } from '@carbon/icons-react'
import '../../styles/components/StatsCards.scss'

const StatsCards = () => {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchStats()
    // Refresh every 30 seconds
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchStats = async () => {
    try {
      // GraphQL query
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
              }
            }
            s3Storage {
              totalAssets
              totalSizeMb
              configured
              images
              pdfs
            }
            totalItems
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
      
      // Transform to match existing component structure
      setStats({
        total_db_records: metrics.localDb.total,
        local_db_records: metrics.localDb.total,
        local_table_counts: {
          document_embeddings: metrics.localDb.tableCounts.documentEmbeddings,
          research_sessions: metrics.localDb.tableCounts.researchSessions,
          experiments: metrics.localDb.tableCounts.experiments
        },
        total_s3_assets: metrics.localDb.tableCounts.digitalAssets,
        total_s3_size_mb: 0,
        s3_configured: true,
        s3_images: metrics.s3Storage.images,
        s3_pdfs: metrics.s3Storage.pdfs,
        total_items: metrics.totalItems
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
      <Column lg={5} md={4} sm={4}>
        <Tile className="stats-card stats-card--database">
          <div className="stats-card__icon">
            <DataBase size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.total_db_records)}
            </div>
            <div className="stats-card__label">Database Records</div>
            {stats?.local_table_counts && (
              <div className="stats-card__breakdown">
                <div>{formatNumber(stats.local_table_counts.document_embeddings)} embeddings</div>
                <div>{formatNumber(stats.local_table_counts.research_sessions)} sessions</div>
                <div>{formatNumber(stats.local_table_counts.experiments)} experiments</div>
              </div>
            )}
          </div>
        </Tile>
      </Column>

      <Column lg={5} md={4} sm={4}>
        <Tile className="stats-card stats-card--storage">
          <div className="stats-card__icon">
            <CloudApp size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.total_s3_assets)}
            </div>
            <div className="stats-card__label">Digital Assets</div>
            <div className="stats-card__breakdown">
              <div>{formatNumber(stats?.s3_images || 0)} images</div>
              <div>{formatNumber(stats?.s3_pdfs || 0)} PDFs</div>
            </div>
          </div>
        </Tile>
      </Column>

      <Column lg={6} md={4} sm={4}>
        <Tile className="stats-card stats-card--total">
          <div className="stats-card__icon">
            <Cube size={32} />
          </div>
          <div className="stats-card__content">
            <div className="stats-card__number">
              {formatNumber(stats?.total_items)}
            </div>
            <div className="stats-card__label">Total Items</div>
            <div className="stats-card__breakdown">
              Combined records & assets
            </div>
          </div>
        </Tile>
      </Column>
    </Grid>
  )
}

export default StatsCards
