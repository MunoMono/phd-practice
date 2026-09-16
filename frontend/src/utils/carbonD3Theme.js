/**
 * Carbon Design System + D3.js Theme Configuration
 * For RCA PhD visualization components
 *
 * D3 scales need resolved color strings, so Carbon palette values are centralized
 * here as the single visualization source of truth. Do not introduce ad hoc hex
 * colors in components; add or change palette values in this file only.
 */

import * as d3 from 'd3'

// Carbon color tokens
export const carbonColors = {
  // Primary palette
  primary: {
    blue: '#0f62fe',
    purple: '#8a3ffc',
    cyan: '#33b1ff',
    teal: '#009d9a',
    magenta: '#ee538b',
  },
  
  // Status colors
  status: {
    success: '#24a148',
    warning: '#f1c21b',
    error: '#da1e28',
    info: '#0f62fe',
  },
  
  // Gray scale
  gray: {
    10: '#f4f4f4',
    20: '#e0e0e0',
    30: '#c6c6c6',
    40: '#a8a8a8',
    50: '#8d8d8d',
    60: '#6f6f6f',
    70: '#525252',
    80: '#393939',
    90: '#262626',
    100: '#161616',
  },
  
  // Extended palette for visualizations
  visualization: [
    '#0f62fe', // Blue
    '#8a3ffc', // Purple
    '#33b1ff', // Cyan
    '#24a148', // Green
    '#f1c21b', // Yellow
    '#da1e28', // Red
    '#ff832b', // Orange
    '#ee538b', // Magenta
    '#009d9a', // Teal
    '#570408', // Dark red
    '#198038', // Dark green
    '#002d9c', // Dark blue
    '#b28600', // Dark yellow
    '#005d5d', // Dark teal
    '#9f1853', // Dark magenta
  ],
  
  // Sequential scales for heatmaps
  sequential: {
    blue: ['#edf5ff', '#d0e2ff', '#a6c8ff', '#78a9ff', '#4589ff', '#0f62fe', '#0043ce', '#002d9c', '#001d6c', '#001141'],
    purple: ['#f6f2ff', '#e8daff', '#d4bbff', '#be95ff', '#a56eff', '#8a3ffc', '#6929c4', '#491d8b', '#31135e', '#1c0f30'],
    teal: ['#d9fbfb', '#9ef0f0', '#3ddbd9', '#08bdba', '#009d9a', '#007d79', '#005d5d', '#004144', '#022b30', '#081a1c'],
  },
  
  // Diverging scales for comparisons
  diverging: {
    purpleToBlue: ['#8a3ffc', '#6929c4', '#491d8b', '#31135e', '#1c0f30', '#001d6c', '#002d9c', '#0043ce', '#0f62fe', '#4589ff'],
    redToGreen: ['#da1e28', '#fa4d56', '#ff832b', '#f1c21b', '#fddc69', '#b8f4b8', '#6fdc8c', '#42be65', '#24a148', '#198038'],
  }
}

export const chartColors = {
  axis: carbonColors.gray[30],
  axisLabel: carbonColors.gray[30],
  axisText: carbonColors.gray[40],
  label: carbonColors.gray[10],
  emptyState: carbonColors.gray[50],
  tooltipBackground: carbonColors.gray[100],
  tooltipText: carbonColors.gray[10],
  selectionStroke: carbonColors.gray[10],
  highlightStroke: carbonColors.status.warning,
  plotStroke: carbonColors.gray[100],
  query: carbonColors.primary.blue,
  model: carbonColors.sequential.blue[4],
  chunk: carbonColors.status.success,
  document: carbonColors.primary.purple,
  pid: carbonColors.status.warning,
  answer: carbonColors.status.error,
  emergent: carbonColors.status.success,
  dialectical: carbonColors.primary.blue,
}

// Carbon typography
export const carbonTypography = {
  fonts: {
    mono: '"IBM Plex Mono", "Menlo", "DejaVu Sans Mono", "Bitstream Vera Sans Mono", Courier, monospace',
    sans: '"IBM Plex Sans", "Helvetica Neue", Arial, sans-serif',
    serif: '"IBM Plex Serif", "Georgia", Times, serif',
  },
  
  sizes: {
    caption: '12px',
    label: '12px',
    helperText: '12px',
    body: '14px',
    heading03: '20px',
    heading04: '28px',
    heading05: '32px',
    heading06: '42px',
  },
  
  weights: {
    light: 300,
    regular: 400,
    semibold: 600,
  }
}

// D3 scale configurations using Carbon colors
export const d3Scales = {
  // Categorical color scale
  categorical: (domain = []) => {
    const scale = d3.scaleOrdinal()
      .range(carbonColors.visualization)

    if (domain.length > 0) {
      scale.domain(domain)
    }

    return scale
  },
  
  // Sequential color scale
  sequential: (scheme = 'blue', domain = [0, 1]) => {
    return d3.scaleSequential()
      .domain(domain)
      .interpolator(d3.interpolateRgbBasis(carbonColors.sequential[scheme]))
  },
  
  // Diverging color scale
  diverging: (scheme = 'purpleToBlue', domain = [-1, 0, 1]) => {
    return d3.scaleDiverging()
      .domain(domain)
      .interpolator(d3.interpolateRgbBasis(carbonColors.diverging[scheme]))
  },
  
  // Size scale for nodes
  nodeSize: (min = 0, max = 1, range = [3, 30]) => {
    return d3.scaleSqrt()
      .domain([min, max])
      .range(range)
  },
  
  // Opacity scale
  opacity: (domain = [0, 1], range = [0.2, 1.0]) => {
    return d3.scaleLinear()
      .domain(domain)
      .range(range)
  }
}

// Chart styling presets
export const chartStyles = {
  network: {
    node: {
      defaultRadius: 8,
      minRadius: 4,
      maxRadius: 24,
      strokeWidth: 2,
      stroke: carbonColors.gray[100],
      hoverStrokeColor: carbonColors.primary.blue,
      selectedStrokeWidth: 3,
    },
    link: {
      strokeWidth: 1.5,
      stroke: carbonColors.gray[40],
      opacity: (weight = 1) => Math.max(0.12, Math.min(0.85, weight * 0.6)),
      hoverStrokeWidth: 3,
      hoverStrokeColor: carbonColors.primary.purple,
    },
    label: {
      fontSize: '11px',
      fontFamily: carbonTypography.fonts.sans,
      fill: carbonColors.gray[100],
      hoverFill: carbonColors.primary.blue,
    }
  },
  
  timeline: {
    axis: {
      stroke: carbonColors.gray[30],
      strokeWidth: 1,
      tickSize: 6,
      tickPadding: 8,
    },
    text: {
      fill: chartColors.axisText,
      fontSize: '12px',
    },
    label: {
      fill: chartColors.axisLabel,
      fontSize: '14px',
    },
    line: {
      strokeWidth: 2,
      strokeLinecap: 'round',
      strokeLinejoin: 'round',
    },
    area: {
      fillOpacity: 0.1,
    },
    points: {
      radius: 4,
      hoverRadius: 6,
    }
  },
  
  heatmap: {
    cell: {
      strokeWidth: 1,
      stroke: carbonColors.gray[10],
      hoverStrokeWidth: 2,
      hoverStroke: carbonColors.gray[100],
    },
    labels: {
      fontSize: '12px',
      fontFamily: carbonTypography.fonts.sans,
    }
  }
};

// Animation configurations
export const animations = {
  duration: {
    fast: 200,
    normal: 400,
    slow: 800,
  },
  
  easing: {
    // D3 easing functions
    default: 'easeCubicOut',
    elastic: 'easeElasticOut',
    bounce: 'easeBounceOut',
  },
  
  transitions: {
    fade: {
      duration: 300,
      opacity: [0, 1],
    },
    slide: {
      duration: 400,
      transform: 'translateY(20px)',
    },
    scale: {
      duration: 300,
      transform: 'scale(0.95)',
    }
  }
}

// Responsive breakpoints (matching Carbon grid)
export const breakpoints = {
  sm: 320,   // Small
  md: 672,   // Medium
  lg: 1056,  // Large
  xlg: 1312, // Extra large
  max: 1584, // Maximum
}

// Layout spacing (Carbon spacing scale)
export const spacing = {
  '01': '2px',
  '02': '4px',
  '03': '8px',
  '04': '12px',
  '05': '16px',
  '06': '24px',
  '07': '32px',
  '08': '40px',
  '09': '48px',
  '10': '64px',
  '11': '80px',
  '12': '96px',
  '13': '160px',
}

// Utility functions
export const utils = {
  // Get color by index with wrapping
  getColorByIndex: (index) => {
    return carbonColors.visualization[index % carbonColors.visualization.length]
  },

  getClusterColorScale: (clusters = [], accessor = (cluster) => cluster?.theme || cluster) => {
    const domain = clusters.map(accessor).filter(Boolean)
    return d3Scales.categorical(domain)
  },

  getClusterColorMap: (clusters = [], accessor = (cluster) => cluster?.theme || cluster) => {
    const scale = utils.getClusterColorScale(clusters, accessor)
    return new Map(
      clusters.map((cluster) => {
        const key = accessor(cluster)
        return [key, scale(key)]
      })
    )
  },
  
  // Get contrasting text color
  getContrastColor: (backgroundColor) => {
    // Simple luminance check
    const color = backgroundColor.replace('#', '');
    const r = parseInt(color.substr(0, 2), 16);
    const g = parseInt(color.substr(2, 2), 16);
    const b = parseInt(color.substr(4, 2), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance > 0.5 ? carbonColors.gray[100] : carbonColors.gray[10]
  },
  
  // Format number with SI suffix
  formatNumber: (num) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  },
  
  // Truncate text with ellipsis
  truncate: (text, maxLength = 50) => {
    if (text.length <= maxLength) return text
    return text.substr(0, maxLength - 3) + '...'
  }
}

export default {
  colors: carbonColors,
  chartColors,
  typography: carbonTypography,
  scales: d3Scales,
  styles: chartStyles,
  animations,
  breakpoints,
  spacing,
  utils
};
