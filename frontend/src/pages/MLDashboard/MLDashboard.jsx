import React, { useState, useEffect } from 'react';
import {
  Grid,
  Column,
  Tile,
  Loading,
  ProgressBar,
  DataTable,
  TableContainer,
  Table,
  TableHead,
  TableRow,
  TableHeader,
  TableBody,
  TableCell,
  Tag,
  Button,
  Tabs,
  TabList,
  Tab,
  TabPanels,
  TabPanel,
} from '@carbon/react';
import {
  Analytics,
  Document,
  ModelAlt,
  DataVis_1,
  Network_3,
  ChartLine,
  Search,
  Renew,
} from '@carbon/icons-react';
import DocumentNetwork from '../../components/visualizations/DocumentNetwork';
import ThemeDistribution from '../../components/visualizations/ThemeDistribution';
import TemporalTrends from '../../components/visualizations/TemporalTrends';
import EntityNetwork from '../../components/visualizations/EntityNetwork';
import './MLDashboard.scss';

const MLDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchDashboardStats();
  }, []);

  const fetchDashboardStats = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/viz/dashboard-stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch dashboard stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await fetch(`${import.meta.env.VITE_API_URL}/api/viz/refresh-stats`, {
        method: 'POST'
      });
      await fetchDashboardStats();
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="ml-dashboard-loading">
        <Loading description="Loading ML Dashboard..." withOverlay={false} />
      </div>
    );
  }

  const completionRate = stats?.mlProcessing?.completionRate || 0;

  return (
    <div className="ml-dashboard">
      <Grid narrow>
        {/* Header */}
        <Column lg={16} md={8} sm={4} className="dashboard-header">
          <div className="header-content">
            <div>
              <h1>ML Processing Dashboard</h1>
              <p className="header-subtitle">
                RCA PhD Research Corpus Analysis & Visualization
              </p>
            </div>
            <Button
              kind="tertiary"
              renderIcon={Renew}
              onClick={handleRefresh}
              disabled={refreshing}
            >
              {refreshing ? 'Refreshing...' : 'Refresh Stats'}
            </Button>
          </div>
        </Column>

        {/* Stats Cards */}
        <Column lg={4} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <Document size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.overview?.totalDocuments || 0}</h3>
              <p className="stats-label">Total Documents</p>
              <p className="stats-meta">{stats?.overview?.totalPdfs || 0} PDFs</p>
            </div>
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <Analytics size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.mlProcessing?.documentsWithEmbeddings || 0}</h3>
              <p className="stats-label">Embeddings Generated</p>
              <ProgressBar
                value={completionRate}
                label={`${completionRate}% Complete`}
                size="sm"
              />
            </div>
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <ModelAlt size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.mlProcessing?.documentsWithEntities || 0}</h3>
              <p className="stats-label">Entities Extracted</p>
              <p className="stats-meta">
                Avg Confidence: {(stats?.mlProcessing?.avgConfidence * 100 || 0).toFixed(1)}%
              </p>
            </div>
          </Tile>
        </Column>

        <Column lg={4} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <DataVis_1 size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.themes?.uniqueThemes || 0}</h3>
              <p className="stats-label">Unique Themes</p>
              <p className="stats-meta">
                Years: {stats?.overview?.yearRange || 'N/A'}
              </p>
            </div>
          </Tile>
        </Column>

        {/* Visualizations Tabs */}
        <Column lg={16} className="visualization-section">
          <Tabs>
            <TabList aria-label="Visualization tabs" contained>
              <Tab renderIcon={Network_3}>Document Network</Tab>
              <Tab renderIcon={DataVis_1}>Theme Distribution</Tab>
              <Tab renderIcon={ChartLine}>Temporal Trends</Tab>
              <Tab renderIcon={Search}>Entity Network</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Tile className="visualization-tile">
                  <h4>Document Similarity Network</h4>
                  <p className="tile-description">
                    Interactive network showing relationships between documents based on semantic similarity,
                    shared themes, and entity overlap. Node size represents PDF count.
                  </p>
                  <DocumentNetwork />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <h4>Theme Distribution Analysis</h4>
                  <p className="tile-description">
                    Distribution of themes across the research corpus. Colors from Carbon Design palette.
                  </p>
                  <ThemeDistribution />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <h4>Publication Timeline</h4>
                  <p className="tile-description">
                    Document publication trends over time with theme evolution.
                  </p>
                  <TemporalTrends />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <h4>Entity Co-occurrence Network</h4>
                  <p className="tile-description">
                    Network of people, organizations, and concepts mentioned across documents.
                  </p>
                  <EntityNetwork />
                </Tile>
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>

        {/* Recent Activity */}
        <Column lg={16}>
          <Tile className="activity-tile">
            <h4>Recent ML Processing Activity</h4>
            <div className="activity-table">
              {stats?.recentActivity && stats.recentActivity.length > 0 ? (
                <DataTable
                  rows={stats.recentActivity.map((activity, index) => ({
                    id: `${activity.stage}-${activity.status}-${index}`,
                    ...activity
                  }))}
                  headers={[
                    { key: 'stage', header: 'Stage' },
                    { key: 'status', header: 'Status' },
                    { key: 'count', header: 'Count' },
                    { key: 'avgDuration', header: 'Avg Duration (s)' },
                  ]}
                >
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer>
                      <Table {...getTableProps()}>
                        <TableHead>
                          <TableRow>
                            {headers.map((header) => (
                              <TableHeader {...getHeaderProps({ header })} key={header.key}>
                                {header.header}
                              </TableHeader>
                            ))}
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {rows.map((row) => (
                            <TableRow {...getRowProps({ row })} key={row.id}>
                              {row.cells.map((cell) => (
                                <TableCell key={cell.id}>
                                  {cell.info.header === 'status' ? (
                                    <Tag
                                      type={
                                        cell.value === 'completed' ? 'green' :
                                        cell.value === 'failed' ? 'red' :
                                        cell.value === 'started' ? 'blue' : 'gray'
                                      }
                                    >
                                      {cell.value}
                                    </Tag>
                                  ) : cell.info.header === 'avgDuration' ? (
                                    cell.value ? cell.value.toFixed(2) : '-'
                                  ) : (
                                    cell.value
                                  )}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </DataTable>
              ) : (
                <p className="no-activity">No recent activity in the last 24 hours</p>
              )}
            </div>
            <p className="activity-footer">
              Last updated: {stats?.lastUpdated ? new Date(stats.lastUpdated).toLocaleString() : 'N/A'}
            </p>
          </Tile>
        </Column>
      </Grid>
    </div>
  );
};

export default MLDashboard;
