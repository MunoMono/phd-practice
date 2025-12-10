import { Grid, Column, Tile, ClickableTile } from '@carbon/react'
import { useNavigate } from 'react-router-dom'
import { ChartNetwork, DataVis_1, Recording, Chemistry } from '@carbon/icons-react'
import TemporalDriftChart from '../../components/visualizations/TemporalDriftChart'
import '../../styles/pages/Dashboard.scss'

const Dashboard = () => {
  const navigate = useNavigate()

  return (
    <div className="dashboard">
      <div className="dashboard__hero">
        <Grid className="dashboard__hero-content">
          <Column lg={10} md={6} sm={4}>
            <h1 className="dashboard__hero-title">
              Epistemic drift detection
            </h1>
            <p className="dashboard__hero-subtitle">
              Second-order cybernetic analysis for AI research transparency.
              Track reasoning paths, analyze collaboration patterns, and monitor temporal drift in real-time.
            </p>
          </Column>
        </Grid>
      </div>

      <Grid className="dashboard__content" fullWidth>
        <Column lg={16} md={8} sm={4}>
          <div className="dashboard__diagram-section">
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
            <p>Visualize reasoning paths from queries to source documents with interactive network graphs</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/sessions')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Recording size={32} />
            </div>
            <h3>Session Recorder</h3>
            <p>Log and analyze human-AI collaboration sessions for interaction patterns</p>
          </ClickableTile>
        </Column>

        <Column lg={8} md={4} sm={4}>
          <ClickableTile onClick={() => navigate('/experiments')} className="dashboard__tile">
            <div className="dashboard__tile-icon">
              <Chemistry size={32} />
            </div>
            <h3>Experimental Log</h3>
            <p>Document experiments and track training metrics over time</p>
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
                  <h4>Presentation Layer</h4>
                  <p>React + Carbon Design System + D3.js for interactive visualizations</p>
                </Tile>
              </Column>
              <Column lg={5} md={8} sm={4}>
                <Tile className="dashboard__info-tile">
                  <h4>Logic Layer</h4>
                  <p>FastAPI + Granite 4.0 H-Small-Instruct (32B/9B parameters)</p>
                </Tile>
              </Column>
              <Column lg={6} md={8} sm={4}>
                <Tile className="dashboard__info-tile">
                  <h4>Data Layer</h4>
                  <p>PostgreSQL with pgvector extension + S3 object storage</p>
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
