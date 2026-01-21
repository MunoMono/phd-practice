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
              <svg viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
                {/* Outer green cube frame */}
                {/* Top face */}
                <path d="M80 120 L200 60 L320 120 L200 180 Z" fill="#42be65" />
                {/* Left face */}
                <path d="M80 120 L80 280 L200 340 L200 180 Z" fill="#24a148" />
                {/* Right face */}
                <path d="M200 180 L200 340 L320 280 L320 120 Z" fill="#3dbb61" />
                
                {/* Middle cyan layer */}
                {/* Top face */}
                <path d="M120 140 L200 100 L280 140 L200 180 Z" fill="#82cfff" />
                {/* Left face */}
                <path d="M120 140 L120 260 L200 300 L200 180 Z" fill="#33b1ff" />
                {/* Right face */}
                <path d="M200 180 L200 300 L280 260 L280 140 Z" fill="#52d1c9" />
                
                {/* Inner blue cube */}
                {/* Top face */}
                <path d="M160 160 L200 140 L240 160 L200 180 Z" fill="#78a9ff" />
                {/* Left face */}
                <path d="M160 160 L160 240 L200 260 L200 180 Z" fill="#0f62fe" />
                {/* Right face */}
                <path d="M200 180 L200 260 L240 240 L240 160 Z" fill="#4589ff" />
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
