import { Grid, Column, Tile, Tag } from '@carbon/react'
import { Chemistry } from '@carbon/icons-react'
import TrainingMetricsChart from '../../components/visualizations/TrainingMetricsChart'
import '../../styles/pages/ExperimentalLog.scss'

const ExperimentalLog = () => {
  return (
    <Grid className="experimental-log" fullWidth>
      <Column lg={16} md={8} sm={4}>
        <div className="log__header">
          <div>
            <h1>Experimental Log</h1>
            <p className="log__description">
              IBM Granite fine-tuning runs with complete provenance. 
              Track which PIDs trained which model version for reproducibility.
            </p>
          </div>
          <Tag type="purple" size="md">
            <Chemistry size={16} /> Training Runs
          </Tag>
        </div>
      </Column>

      <Column lg={16} md={8} sm={4}>
        <Tile className="log__chart-tile">
          <h3>Training Loss Curves</h3>
          <TrainingMetricsChart />
        </Tile>
      </Column>

      <Column lg={16} md={8} sm={4}>
        <Tile>
          <h3>Training Run Provenance</h3>
          <p className="log__note">
            Connects to <code>/api/provenance/training/*</code> endpoints to display:
            <br/>• Which PIDs were used in each training run
            <br/>• Corpus snapshot checksums for reproducibility
            <br/>• Hyperparameters, loss curves, and evaluation metrics
            <br/>• Dataset versions for academic peer review
          </p>
        </Tile>
      </Column>
    </Grid>
  )
}

export default ExperimentalLog
