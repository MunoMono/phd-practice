import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from 'recharts'

const chartColors = ['#0f62fe', '#198038', '#8a3ffc', '#525252']

const AtlasCoverageChart = ({ scope = {}, visiblePointCount = 0 }) => {
  const data = [
    { label: 'Local documents', value: scope.totalDocumentsInDb || 0 },
    { label: 'Text extracted', value: scope.documentsWithExtractedText || 0 },
    { label: 'Embedded chunks', value: scope.embeddedChunks || 0 },
    { label: 'Visible points', value: visiblePointCount }
  ]

  return (
    <div className="atlas-coverage-chart" aria-label="Evidence surface coverage chart">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ top: 8, right: 16, bottom: 8, left: 112 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="label" width={108} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [value, 'Records']} />
          <Bar dataKey="value" radius={[0, 2, 2, 0]}>
            {data.map((entry, index) => <Cell key={entry.label} fill={chartColors[index]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default AtlasCoverageChart