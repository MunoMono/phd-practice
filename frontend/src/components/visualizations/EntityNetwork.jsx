import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import { Loading, Tag } from '@carbon/react';
import { carbonColors, d3Scales, chartStyles, animations } from '../../utils/carbonD3Theme';
import './EntityNetwork.scss';

const EntityNetwork = () => {
  const svgRef = useRef();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [selectedType, setSelectedType] = useState(null);

  useEffect(() => {
    fetchEntityData();
    
    const resizeObserver = new ResizeObserver(entries => {
      for (let entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width, height: Math.max(height, 500) });
      }
    });

    if (svgRef.current?.parentElement) {
      resizeObserver.observe(svgRef.current.parentElement);
    }

    return () => resizeObserver.disconnect();
  }, []);

  useEffect(() => {
    if (data && dimensions.width > 0) {
      renderNetwork();
    }
  }, [data, dimensions, selectedType]);

  const fetchEntityData = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/viz/entity-network`);
      const entityData = await response.json();
      setData(entityData);
    } catch (error) {
      console.error('Failed to fetch entity network:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderNetwork = () => {
    if (!data || !svgRef.current) return;

    const { width, height } = dimensions;
    const margin = { top: 20, right: 20, bottom: 20, left: 20 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;

    // Filter data by selected type
    const filteredNodes = selectedType 
      ? data.nodes.filter(n => n.entity_type === selectedType)
      : data.nodes;

    const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = data.links.filter(l => 
      filteredNodeIds.has(l.source) && filteredNodeIds.has(l.target)
    );

    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height)
      .attr('viewBox', [0, 0, width, height]);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Zoom
    const zoom = d3.zoom()
      .scaleExtent([0.5, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });

    svg.call(zoom);

    // Color scale by entity type
    const typeColors = {
      'PERSON': carbonColors.primary,
      'ORG': carbonColors.purple,
      'CONCEPT': carbonColors.teal,
      'METHOD': carbonColors.cyan,
      'LOCATION': carbonColors.magenta
    };

    // Size scale based on frequency
    const sizeScale = d3Scales.nodeSize(
      Math.min(...filteredNodes.map(n => n.frequency)),
      Math.max(...filteredNodes.map(n => n.frequency))
    );

    // Force simulation
    const simulation = d3.forceSimulation(filteredNodes)
      .force('link', d3.forceLink(filteredLinks)
        .id(d => d.id)
        .distance(d => 100 - (d.weight * 30))
      )
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(innerWidth / 2, innerHeight / 2))
      .force('collision', d3.forceCollide().radius(d => sizeScale(d.frequency) + 10));

    // Draw links
    const link = g.append('g')
      .attr('class', 'links')
      .selectAll('line')
      .data(filteredLinks)
      .join('line')
      .attr('stroke', carbonColors.gray[40])
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', d => Math.sqrt(d.weight) * 2);

    // Draw nodes
    const node = g.append('g')
      .attr('class', 'nodes')
      .selectAll('circle')
      .data(filteredNodes)
      .join('circle')
      .attr('r', d => sizeScale(d.frequency))
      .attr('fill', d => typeColors[d.entity_type] || carbonColors.gray[50])
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .call(drag(simulation));

    // Add labels for high-frequency entities
    const label = g.append('g')
      .attr('class', 'labels')
      .selectAll('text')
      .data(filteredNodes.filter(d => d.frequency > 2))
      .join('text')
      .text(d => d.entity_text.length > 20 ? d.entity_text.substring(0, 20) + '...' : d.entity_text)
      .attr('font-size', '11px')
      .attr('fill', carbonColors.gray[100])
      .attr('text-anchor', 'middle')
      .attr('dy', d => sizeScale(d.frequency) + 12)
      .style('pointer-events', 'none')
      .style('font-weight', '500');

    // Tooltip
    const tooltip = d3.select('body')
      .append('div')
      .attr('class', 'entity-tooltip')
      .style('opacity', 0)
      .style('position', 'absolute')
      .style('background-color', carbonColors.gray[100])
      .style('color', carbonColors.gray[10])
      .style('padding', '12px')
      .style('border-radius', '4px')
      .style('font-family', 'IBM Plex Sans')
      .style('font-size', '14px')
      .style('pointer-events', 'none')
      .style('z-index', 1000);

    // Node interactions
    node
      .on('mouseover', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', sizeScale(d.frequency) * 1.3)
          .attr('stroke-width', 3);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 1);
        
        tooltip.html(`
          <strong>${d.entity_text}</strong><br/>
          Type: ${d.entity_type}<br/>
          Frequency: ${d.frequency}<br/>
          Documents: ${d.document_count}
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 10) + 'px');

        // Highlight connected entities
        const connectedIds = new Set();
        filteredLinks.forEach(l => {
          if (l.source.id === d.id) connectedIds.add(l.target.id);
          if (l.target.id === d.id) connectedIds.add(l.source.id);
        });

        node.style('opacity', n => 
          n.id === d.id || connectedIds.has(n.id) ? 1 : 0.2
        );

        link.style('opacity', l => 
          l.source.id === d.id || l.target.id === d.id ? 0.8 : 0.1
        );

        label.style('opacity', labelData =>
          labelData.id === d.id || connectedIds.has(labelData.id) ? 1 : 0.2
        );
      })
      .on('mouseout', function(event, d) {
        d3.select(this)
          .transition()
          .duration(animations.duration.fast)
          .attr('r', sizeScale(d.frequency))
          .attr('stroke-width', 2);

        tooltip.transition()
          .duration(animations.duration.fast)
          .style('opacity', 0);

        node.style('opacity', 1);
        link.style('opacity', 0.6);
        label.style('opacity', 1);
      });

    // Update positions on tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      label
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

    // Drag behavior
    function drag(simulation) {
      function dragstarted(event) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        event.subject.fx = event.subject.x;
        event.subject.fy = event.subject.y;
      }

      function dragged(event) {
        event.subject.fx = event.x;
        event.subject.fy = event.y;
      }

      function dragended(event) {
        if (!event.active) simulation.alphaTarget(0);
        event.subject.fx = null;
        event.subject.fy = null;
      }

      return d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended);
    }

    // Cleanup
    return () => {
      tooltip.remove();
    };
  };

  if (loading) {
    return (
      <div className="entity-loading">
        <Loading description="Loading entity network..." withOverlay={false} />
      </div>
    );
  }

  if (!data || data.nodes.length === 0) {
    return (
      <div className="entity-empty">
        <p>No entity data available. Extract entities from documents to see the network.</p>
      </div>
    );
  }

  const entityTypes = [...new Set(data.nodes.map(n => n.entity_type))];
  const typeColors = {
    'PERSON': 'blue',
    'ORG': 'purple',
    'CONCEPT': 'teal',
    'METHOD': 'cyan',
    'LOCATION': 'magenta'
  };

  return (
    <div className="entity-network">
      <div className="entity-filters">
        <div className="filter-label">Filter by type:</div>
        <Tag
          type="gray"
          size="sm"
          filter={selectedType !== null}
          onClick={() => setSelectedType(null)}
        >
          All ({data.nodes.length})
        </Tag>
        {entityTypes.map(type => (
          <Tag
            key={type}
            type={selectedType === type ? typeColors[type] : 'gray'}
            size="sm"
            filter={selectedType === type}
            onClick={() => setSelectedType(selectedType === type ? null : type)}
          >
            {type} ({data.nodes.filter(n => n.entity_type === type).length})
          </Tag>
        ))}
      </div>
      <svg ref={svgRef} />
    </div>
  );
};

export default EntityNetwork;
