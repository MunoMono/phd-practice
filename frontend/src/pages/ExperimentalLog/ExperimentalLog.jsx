import { Tile, Tag } from '@carbon/react'
import { Chemistry } from '@carbon/icons-react'
import PageHeader from '../../components/layout/PageHeader'
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid'
import TrainingMetricsChart from '../../components/visualizations/TrainingMetricsChart'

const ExperimentalLog = () => {
  return (
    <PageGrid className="experimental-log">
      <Column>
        <PageHeader
          title="Experimental log"
          description="Historical model fine-tuning runs with complete provenance. Track which PIDs trained which model version for reproducibility."
          actions={(
            <Tag type="purple" size="md">
              <Chemistry size={16} /> Training runs
            </Tag>
          )}
        />
      </Column>

      <Column>
        <Tile className="log__chart-tile">
          <h3>Training loss curves</h3>
          <TrainingMetricsChart />
        </Tile>
      </Column>

      <Column>
        <Tile>
          <h3>Training run provenance</h3>
          <p className="log__note">
            Connects to <code>/api/provenance/training/*</code> endpoints to display:
          </p>
          <div className="log__bullet-item log__bullet-item--first">
            • Which PIDs were used in each training run
          </div>
          <div className="log__bullet-item">
            • Corpus snapshot checksums for reproducibility
          </div>
          <div className="log__bullet-item">
            • Hyperparameters, loss curves, and evaluation metrics
          </div>
          <div className="log__bullet-item">
            • Dataset versions for academic peer review
          </div>
        </Tile>
      </Column>
    </PageGrid>
  )
}

export default ExperimentalLog
