import {
  ArrowsHorizontal,
  Catalog,
  CheckmarkOutline,
  Chip,
  DataVis_4,
  Search,
  WarningAlt,
} from '@carbon/icons-react'

export const PRIMARY_SECTIONS = [
  { key: 'workbench', label: 'Workbench', path: '/workbench', icon: Chip },
  { key: 'sources', label: 'Sources', path: '/sources', icon: Search },
  { key: 'analysis', label: 'Analysis', path: '/source-interrogation', icon: DataVis_4 },
  { key: 'visual-analytics', label: 'Visual analytics', path: '/semantic-atlas', icon: DataVis_4 },
  { key: 'evidence', label: 'Evidence', path: '/claims-evidence', icon: CheckmarkOutline },
  { key: 'documentation', label: 'Documentation', path: '/documentation', icon: Catalog },
]

export const SECONDARY_SECTIONS = {
  workbench: [
    { key: 'dashboard', label: 'Dashboard', path: '/workbench', icon: Chip, matches: ['/', '/workbench', '/dashboard'] },
  ],
  sources: [
    { key: 'sources', label: 'Sources', path: '/sources', icon: Search, matches: ['/sources', '/corpus'] },
  ],
  analysis: [
    { key: 'source-interrogation', label: 'Source interrogation', path: '/source-interrogation', icon: Search, matches: ['/source-interrogation', '/ask', '/tracer'] },
    { key: 'absences', label: 'Absences', path: '/absences', icon: WarningAlt, matches: ['/absences', '/missingness'] },
    { key: 'cross-readings', label: 'Cross-readings', path: '/cross-readings', icon: ArrowsHorizontal, matches: ['/cross-readings', '/cross-read'] },
  ],
  'visual-analytics': [
    { key: 'semantic-atlas', label: 'Semantic atlas', path: '/semantic-atlas', icon: DataVis_4, matches: ['/semantic-atlas', '/clusters', '/visual-analytics'] },
    { key: 'semantic-neighbourhoods', label: 'Semantic neighbourhoods', path: '/semantic-neighbourhoods', icon: Search, matches: ['/semantic-neighbourhoods'] },
    { key: 'comparative-views', label: 'Comparative views', path: '/comparative-views', icon: ArrowsHorizontal, matches: ['/comparative-views'] },
    { key: 'temporal-documentary-change', label: 'Temporal change', path: '/temporal-documentary-change', icon: DataVis_4, matches: ['/temporal-documentary-change'] },
    { key: 'critical-inquiry', label: 'Critical inquiry', path: '/critical-inquiry', icon: WarningAlt, matches: ['/critical-inquiry'] },
    { key: 'challenge-map', label: 'Challenge this map', path: '/challenge-map', icon: DataVis_4, matches: ['/challenge-map'] },
  ],
  evidence: [
    { key: 'claims-evidence', label: 'Claims and evidence', path: '/claims-evidence', icon: CheckmarkOutline, matches: ['/claims-evidence', '/claims'] },
    { key: 'research-runs', label: 'Research runs', path: '/research-runs', icon: Catalog, matches: ['/research-runs', '/experiments'] },
    { key: 'provenance', label: 'Provenance', path: '/provenance', icon: Catalog, matches: ['/provenance', '/audit', '/sessions', '/experiments', '/ml-dashboard'] },
  ],
  documentation: [
    { key: 'expanded-abstract', label: 'Expanded abstract', path: '/documentation/expanded-abstract', icon: Catalog, matches: ['/documentation/expanded-abstract'] },
    { key: 'technology-statement-of-work', label: 'Technology Statement of Work', path: '/documentation/technology-statement-of-work', icon: Catalog, matches: ['/documentation/technology-statement-of-work'] },
  ],
}

const PRIMARY_ROUTE_MATCHERS = [
  { key: 'workbench', matches: ['/', '/workbench', '/dashboard'] },
  { key: 'sources', matches: ['/sources', '/corpus'] },
  { key: 'analysis', matches: ['/source-interrogation', '/ask', '/tracer', '/absences', '/missingness', '/cross-readings', '/cross-read'] },
  { key: 'visual-analytics', matches: ['/semantic-atlas', '/clusters', '/visual-analytics', '/semantic-neighbourhoods', '/comparative-views', '/temporal-documentary-change', '/critical-inquiry', '/challenge-map'] },
  { key: 'evidence', matches: ['/claims-evidence', '/claims', '/research-runs', '/experiments', '/provenance', '/audit', '/sessions', '/ml-dashboard'] },
  { key: 'documentation', matches: ['/documentation'] },
]

const pathMatches = (pathname, matches = []) => matches.some((match) => pathname === match || pathname.startsWith(`${match}/`))

export const getNavigationContext = (pathname) => {
  const matchedPrimary = PRIMARY_ROUTE_MATCHERS.find((section) => pathMatches(pathname, section.matches))
  const primarySection = PRIMARY_SECTIONS.find((section) => section.key === matchedPrimary?.key) ?? PRIMARY_SECTIONS[0]
  const secondaryItems = SECONDARY_SECTIONS[primarySection.key] ?? []
  const activeSecondaryItem = secondaryItems.find((item) => pathMatches(pathname, item.matches)) ?? null

  return {
    primarySection,
    secondaryItems,
    activeSecondaryItem,
    breadcrumbs: activeSecondaryItem
      ? [
          { key: primarySection.key, label: primarySection.label, path: primarySection.path },
          { key: activeSecondaryItem.key, label: activeSecondaryItem.label, path: activeSecondaryItem.path },
        ]
      : primarySection.key !== 'workbench'
        ? [{ key: primarySection.key, label: primarySection.label, path: primarySection.path }]
        : [],
  }
}