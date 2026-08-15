import React, { useState, useEffect } from 'react';
import {
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
import PanelHeader from '../../components/layout/PanelHeader';
import PageHeader from '../../components/layout/PageHeader';
import { PageGrid, PageColumn as Column } from '../../components/layout/PageGrid';
import DocumentNetwork from '../../components/visualizations/DocumentNetwork';
import ThemeDistribution from '../../components/visualizations/ThemeDistribution';
import TemporalTrends from '../../components/visualizations/TemporalTrends';
import EntityNetwork from '../../components/visualizations/EntityNetwork';
import GraniteChatPanel from './GraniteChatPanel';
import {
  fetchDashboardStats as fetchDashboardStatsData,
  refreshDashboardStats as refreshDashboardStatsData
} from '../../api/viz';

const MLDashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDashboardStats();
  }, []);

  const loadDashboardStats = async () => {
    try {
      const data = await fetchDashboardStatsData();
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
      await refreshDashboardStatsData();
      await loadDashboardStats();
    } catch (error) {
      console.error('Failed to refresh stats:', error);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="ml-dashboard-loading">
        <Loading description="Loading ML dashboard..." withOverlay={false} />
      </div>
    );
  }

  const completionRate = stats?.mlProcessing?.completionRate || 0;

  return (
    <div className="ml-dashboard">
      <PageGrid>
        <Column className="dashboard-header">
          <PageHeader
            title="ML processing dashboard"
            description="RCA PhD research corpus analysis and visualization."
            actions={(
              <Button
                kind="tertiary"
                renderIcon={Renew}
                onClick={handleRefresh}
                disabled={refreshing}
              >
                {refreshing ? 'Refreshing...' : 'Refresh stats'}
              </Button>
            )}
          />
        </Column>

        {/* Stats Cards */}
        <Column lg={7} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <Document size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.overview?.totalDocuments || 0}</h3>
              <p className="stats-label">Total documents</p>
              <p className="stats-meta">{stats?.overview?.totalPdfs || 0} PDFs indexed</p>
            </div>
          </Tile>
        </Column>

        <Column lg={7} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <Analytics size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.mlProcessing?.documentsWithEmbeddings || 0}</h3>
              <p className="stats-label">Embeddings generated</p>
              <ProgressBar
                value={completionRate}
                label={`${completionRate}% Complete`}
                size="sm"
              />
            </div>
          </Tile>
        </Column>

        <Column lg={7} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <ModelAlt size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.mlProcessing?.documentsWithEntities || 0}</h3>
              <p className="stats-label">Entities extracted</p>
              <p className="stats-meta">
                Avg Confidence: {((stats?.mlProcessing?.avgConfidence || 0) * 100).toFixed(1)}%
              </p>
            </div>
          </Tile>
        </Column>

        <Column lg={7} md={4} sm={4}>
          <Tile className="stats-tile">
            <div className="stats-icon">
              <DataVis_1 size={32} />
            </div>
            <div className="stats-content">
              <h3 className="stats-number">{stats?.themes?.uniqueThemes || 0}</h3>
              <p className="stats-label">Unique themes</p>
              <p className="stats-meta">
                Years: {stats?.overview?.yearRange || 'N/A'}
              </p>
            </div>
          </Tile>
        </Column>

        {/* Visualizations Tabs */}
        <Column className="visualization-section">
          <Tabs>
            <TabList aria-label="Visualization tabs" contained>
              <Tab renderIcon={Network_3}>Document network</Tab>
              <Tab renderIcon={DataVis_1}>Theme distribution</Tab>
              <Tab renderIcon={ChartLine}>Temporal trends</Tab>
              <Tab renderIcon={Search}>Entity network</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Tile className="visualization-tile">
                  <PanelHeader
                    title="Document similarity network"
                    description="Interactive network showing relationships between documents based on semantic similarity, shared themes, and entity overlap. Node size represents PDF count."
                    className="visualization-tile__header"
                  />
                  <DocumentNetwork />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <PanelHeader
                    title="Theme distribution analysis"
                    description="Distribution of themes across the research corpus. Colors from Carbon Design palette."
                    className="visualization-tile__header"
                  />
                  <ThemeDistribution />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <PanelHeader
                    title="Publication timeline"
                    description="Document publication trends over time with theme evolution."
                    className="visualization-tile__header"
                  />
                  <TemporalTrends />
                </Tile>
              </TabPanel>
              
              <TabPanel>
                <Tile className="visualization-tile">
                  <PanelHeader
                    title="Entity co-occurrence network"
                    description="Network of people, organizations, and concepts mentioned across documents."
                    className="visualization-tile__header"
                  />
                  <EntityNetwork />
                </Tile>
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Column>

        <Column>
          <GraniteChatPanel />
        </Column>

        {/* Recent Activity */}
        <Column>
          <Tile className="activity-tile">
            <PanelHeader title="Recent ML processing activity" className="activity-tile__header" />
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
                    { key: 'avgDuration', header: 'Avg duration (s)' },
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
                <p className="no-activity">No recent activity in the last 24 hours.</p>
              )}
            </div>
            <p className="activity-footer">
              Last updated: {stats?.lastUpdated ? new Date(stats.lastUpdated).toLocaleString() : 'N/A'}
            </p>
          </Tile>
        </Column>
      </PageGrid>
    </div>
  );
};

export default MLDashboard;
