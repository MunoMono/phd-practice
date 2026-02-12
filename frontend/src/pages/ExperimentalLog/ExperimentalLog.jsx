import { Grid, Column, Tile, Tag } from '@carbon/react'
import { Chemistry } from '@carbon/icons-react'
import TrainingMetricsChart from '../../components/visualizations/TrainingMetricsChart'
import '../../styles/pages/ExperimentalLog.scss'

const ExperimentalLog = () => {
  return (
    <Grid narrow className="experimental-log">
      <Column lg={16} md={8} sm={4}>
        <div className="log__header">
          <div>
            <h1>Experimental log</h1>
            <p className="log__description">
              IBM Granite fine-tuning runs with complete provenance. 
              Track which PIDs trained which model version for reproducibility.
            </p>
          </div>
          <Tag type="purple" size="md">
            <Chemistry size={16} /> Training runs
          </Tag>
        </div>
      </Column>

      <Column lg={16} md={8} sm={4}>
        <Tile className="log__chart-tile">
          <h3>Training loss curves</h3>
          <TrainingMetricsChart />
        </Tile>
      </Column>

      <Column lg={16} md={8} sm={4}>
        <Tile>
          <h3>Training run provenance</h3>
          <p className="log__note">
            Connects to <code>/api/provenance/training/*</code> endpoints to display:
          </p>
          <div style={{ paddingLeft: '28px', textIndent: '-16px', marginTop: '12px' }}>
            • Which PIDs were used in each training run
          </div>
          <div style={{ paddingLeft: '28px', textIndent: '-16px' }}>
            • Corpus snapshot checksums for reproducibility
          </div>
          <div style={{ paddingLeft: '28px', textIndent: '-16px' }}>
            • Hyperparameters, loss curves, and evaluation metrics
          </div>
          <div style={{ paddingLeft: '28px', textIndent: '-16px' }}>
            • Dataset versions for academic peer review
          </div>
        </Tile>
      </Column>
    </Grid>
  )
}

export default ExperimentalLog
