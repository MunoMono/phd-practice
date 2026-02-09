import { Grid, Column, Tile, ClickableTile, Tag } from '@carbon/react'
import { useNavigate } from 'react-router-dom'
import { ChartNetwork, DataVis_1, Recording, Chemistry, Checkmark, InProgress, Chip } from '@carbon/icons-react'
import { useEffect, useState } from 'react'
import TemporalDriftChart from '../../components/visualizations/TemporalDriftChart'
import StatsCards from '../../components/StatsCards/StatsCards'
import '../../styles/pages/Dashboard.scss'

const Dashboard = () => {
  const navigate = useNavigate()
  const [graniteInfo, setGraniteInfo] = useState(null)

  useEffect(() => {
    fetch('/api/granite/model-info')
      .then(res => res.json())
      .then(data => setGraniteInfo(data))
      .catch(err => console.error('Failed to fetch Granite model info:', err))
  }, [])

  return (
    <div className="dashboard">
      <Grid narrow>
        {/* Hero Section */}
        <Column lg={16} md={8} sm={4}>
          <div className="dashboard__hero">
            <div className="dashboard__hero-wrapper">
              <h1 className="dashboard__hero-title">
                Epistemic drift detection
              </h1>
              <p className="dashboard__hero-subtitle">
                PID-gated NLP for Royal College of Art's Department of Design Research (DDR, 1965-1985). 
                BERT embeddings + provenance tracking + IBM Granite fine-tuning with full academic attribution.
              </p>
            </div>
          </div>
        </Column>
        {/* Granite Hero Section */}
        <Column lg={6} md={4} sm={4}>
              <div className="dashboard__granite-hero-logo">
                <img src="/granite-logo.png" alt="IBM Granite" />
              </div>
            </Column>
        <Column lg={10} md={4} sm={4}>
          <div className="dashboard__granite-hero-content">
                <div className="dashboard__granite-hero-badge">
                  <Tag type="blue" size="md">
                    <Chip size={20} /> Powered by IBM Granite
                  </Tag>
                  {graniteInfo && (
                    <Tag type={graniteInfo.is_loaded ? 'green' : 'gray'} size="md">
                      {graniteInfo.is_loaded ? <Checkmark size={16} /> : <InProgress size={16} />}
                      {graniteInfo.is_loaded ? ' Active' : ' Standby'}
                    </Tag>
                  )}
                </div>
                <h2 className="dashboard__granite-hero-title">
                  Enterprise AI for academic research
                </h2>
                <p className="dashboard__granite-hero-description">
                  IBM Granite is a family of open, performant, and trusted AI models purpose-built for business and optimized for 
                  scientific tasks. This research platform leverages <strong>Granite 3.1 8B Instruct</strong> with 8-bit quantization 
                  for efficient CPU-based inference, enabling epistemic drift detection across historical design methods literature 
                  (1965-1985) with full provenance tracking and formal academic attribution.
                </p>
                {graniteInfo && (
                  <div className="dashboard__granite-hero-specs">
                    <div className="dashboard__granite-hero-spec">
                      <span className="dashboard__granite-hero-spec-label">Model</span>
                      <span className="dashboard__granite-hero-spec-value">{graniteInfo.model_name || 'granite-3.1-8b-instruct'}</span>
                    </div>
                    <div className="dashboard__granite-hero-spec">
                      <span className="dashboard__granite-hero-spec-label">Device</span>
                      <span className="dashboard__granite-hero-spec-value">{graniteInfo.device || 'CPU'}</span>
                    </div>
                    {graniteInfo.config && (
                      <>
                        <div className="dashboard__granite-hero-spec">
                          <span className="dashboard__granite-hero-spec-label">Max Tokens</span>
                          <span className="dashboard__granite-hero-spec-value">{graniteInfo.config.max_tokens}</span>
                        </div>
                        <div className="dashboard__granite-hero-spec">
                          <span className="dashboard__granite-hero-spec-label">Temperature</span>
                          <span className="dashboard__granite-hero-spec-value">{graniteInfo.config.temperature}</span>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <h2 className="dashboard__section-title">System metrics</h2>
        </Column>
        
        <Column lg={16} md={8} sm={4}>
          <StatsCards />
        </Column>

        <Column lg={16} md={8} sm={4}>
          <div className="dashboard__diagram-section">
            <Tag type="blue" size="md" className="dashboard__diagram-badge">
              <Checkmark size={16} /> PID-Gated Architecture
            </Tag>
            <img 
              src="/diagrams/home/phd-model.svg" 
              alt="PhD research framework diagram showing the three strands of research"
              className="dashboard__diagram"
            />
          </div>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <h2 className="dashboard__section-title">Research tools</h2>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/tracer')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <ChartNetwork size={32} />
            </div>
            <h3>Evidence tracer</h3>
            <p>Trace predictions to archival sources with formal citations. Full provenance: Embeddings → Chunks → PIDs → DDR Archive</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/sessions')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Recording size={32} />
            </div>
            <h3>Session recorder</h3>
            <p>Inference logging for XAI. Every prediction attributed to source chunks for supervisor validation</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/experiments')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Chemistry size={32} />
            </div>
            <h3>Experimental log</h3>
            <p>IBM Granite training runs with provenance. Track which PIDs trained which model for reproducibility</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard__tile dashboard__tile--static">
            <div className="dashboard__tile-icon">
              <DataVis_1 size={32} />
            </div>
            <h3>Temporal analysis</h3>
            <p>Monitor epistemic drift patterns and model behavior changes</p>
          </Tile>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <Tile className="dashboard__chart-tile">
            <h3 className="dashboard__chart-title">Temporal drift analysis</h3>
            <TemporalDriftChart />
          </Tile>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <h2 className="dashboard__section-title">System architecture</h2>
        </Column>
        
        <Column lg={5} md={8} sm={4}>
          <Tile className="dashboard__info-tile">
            <h4>Ingestion layer</h4>
            <p>PID-gated allowlist: GraphQL sync + S3 validation + Docling OCR (PDF/TIFF)</p>
          </Tile>
        </Column>
        <Column lg={5} md={8} sm={4}>
          <Tile className="dashboard__info-tile">
            <h4>NLP layer</h4>
            <p>BERT embeddings (384-dim) + IBM Granite fine-tuning + pgvector similarity search</p>
          </Tile>
        </Column>
        <Column lg={6} md={8} sm={4}>
          <Tile className="dashboard__info-tile">
            <h4>Provenance layer</h4>
            <p>Training runs + inference logs + corpus snapshots + formal citations</p>
          </Tile>
        </Column>
      </Grid>
    </div>
  )
}

export default Dashboard
