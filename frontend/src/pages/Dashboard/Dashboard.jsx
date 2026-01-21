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
      <div className="dashboard__hero">
        <Grid className="dashboard__hero-content">
          <Column lg={10} md={6} sm={4}>
            <h1 className="dashboard__hero-title">
              Epistemic drift detection
            </h1>
            <p className="dashboard__hero-subtitle">
              PID-gated NLP for design methods research (1965-1985). 
              BERT embeddings + provenance tracking + IBM Granite fine-tuning with full academic attribution.
            </p>
          </Column>
        </Grid>
      </div>

      <Grid className="dashboard__content" fullWidth>
        {/* Granite Hero Section */}
        <Column lg={16} md={8} sm={4}>
          <div className="dashboard__granite-hero">
            <div className="dashboard__granite-hero-logo">
              <svg viewBox="0 0 720 720" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{stopColor: '#00c896', stopOpacity: 1}} />
                    <stop offset="100%" style={{stopColor: '#00d084', stopOpacity: 1}} />
                  </linearGradient>
                  <linearGradient id="grad2" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" style={{stopColor: '#0f62fe', stopOpacity: 1}} />
                    <stop offset="100%" style={{stopColor: '#4589ff', stopOpacity: 1}} />
                  </linearGradient>
                  <linearGradient id="grad3" x1="0%" y1="100%" x2="0%" y2="0%">
                    <stop offset="0%" style={{stopColor: '#00c896', stopOpacity: 1}} />
                    <stop offset="100%" style={{stopColor: '#42be65', stopOpacity: 1}} />
                  </linearGradient>
                </defs>
                {/* Front face - light mint */}
                <path d="M220 280 L500 140 L500 440 L220 580 Z" fill="#d0f0e0" />
                {/* Top face - green gradient */}
                <path d="M220 280 L500 140 L500 160 L360 240 L360 460 L220 540 Z" fill="url(#grad1)" />
                {/* Left face - dark green */}
                <path d="M53 160 L220 75 L220 580 L53 495 Z" fill="#006d32" />
                {/* Right face - cyan gradient */}
                <path d="M500 140 L667 225 L667 525 L500 440 Z" fill="#52d1c9" />
                {/* Top plane - light green gradient */}
                <path d="M220 75 L500 160 L667 225 L387 140 Z" fill="url(#grad3)" opacity="0.9" />
                {/* Inner cube - blue gradient */}
                <path d="M230 320 L360 240 L445 290 L315 370 Z" fill="url(#grad2)" />
                <path d="M360 240 L360 460 L445 510 L445 290 Z" fill="#0043ce" />
                <path d="M315 370 L445 290 L445 510 L315 590 Z" fill="#4589ff" opacity="0.9" />
              </svg>
            </div>
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
                Enterprise AI for Academic Research
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
          </div>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <h2 className="dashboard__section-title">System Metrics</h2>
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
          <h2 className="dashboard__section-title">Research Tools</h2>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/tracer')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <ChartNetwork size={32} />
            </div>
            <h3>Evidence Tracer</h3>
            <p>Trace predictions to archival sources with formal citations. Full provenance: Embeddings → Chunks → PIDs → DDR Archive</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/sessions')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Recording size={32} />
            </div>
            <h3>Session Recorder</h3>
            <p>Inference logging for XAI. Every prediction attributed to source chunks for supervisor validation</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/experiments')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Chemistry size={32} />
            </div>
            <h3>Experimental Log</h3>
            <p>IBM Granite training runs with provenance. Track which PIDs trained which model for reproducibility</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <Tile className="dashboard__tile dashboard__tile--static">
            <div className="dashboard__tile-icon">
              <DataVis_1 size={32} />
            </div>
            <h3>Temporal Analysis</h3>
            <p>Monitor epistemic drift patterns and model behavior changes</p>
          </Tile>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <Tile className="dashboard__chart-tile">
            <h3 className="dashboard__chart-title">Temporal Drift Analysis</h3>
            <TemporalDriftChart />
          </Tile>
        </Column>

        <Column lg={16} md={8} sm={4}>
          <div className="dashboard__info-section">
            <h2 className="dashboard__section-title">System Architecture</h2>
            <Grid condensed>
              <Column lg={5} md={8} sm={4}>
                <Tile className="dashboard__info-tile">
                  <h4>Ingestion Layer</h4>
                  <p>PID-gated allowlist: GraphQL sync + S3 validation + Docling OCR (PDF/TIFF)</p>
                </Tile>
              </Column>
              <Column lg={5} md={8} sm={4}>
                <Tile className="dashboard__info-tile">
                  <h4>NLP Layer</h4>
                  <p>BERT embeddings (384-dim) + IBM Granite fine-tuning + pgvector similarity search</p>
                </Tile>
              </Column>
              <Column lg={6} md={8} sm={4}>
                <Tile className="dashboard__info-tile">
                  <h4>Provenance Layer</h4>
                  <p>Training runs + inference logs + corpus snapshots + formal citations</p>
                </Tile>
              </Column>
            </Grid>
          </div>
        </Column>
      </Grid>
    </div>
  )
}

export default Dashboard
