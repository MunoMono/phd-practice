-- Sample data for production database
-- Insert sample document embedding
INSERT INTO document_embeddings (id, document_id, content, embedding, metadata, created_at)
VALUES (
    gen_random_uuid(),
    'sample-doc-001',
    'This is a sample research document about testamentary traces in AI systems.',
    '[0.1, 0.2, 0.3]'::vector,
    '{"source": "research_paper", "topic": "testamentary-traces"}'::jsonb,
    NOW()
);

-- Insert sample research session
INSERT INTO research_sessions (id, session_name, start_time, metadata)
VALUES (
    gen_random_uuid(),
    'AI Ethics Research Session',
    NOW() - INTERVAL '2 hours',
    '{"researcher": "Production Test", "focus": "testamentary traces patterns"}'::jsonb
);

-- Insert sample experiment
INSERT INTO experiments (id, experiment_name, hypothesis, results, created_at)
VALUES (
    gen_random_uuid(),
    'Temporal Drift Analysis',
    'AI models exhibit measurable testamentary traces over extended deployment periods',
    '{"drift_detected": true, "confidence": 0.87}'::jsonb,
    NOW() - INTERVAL '1 day'
);

-- Insert sample digital assets
INSERT INTO digital_assets (id, asset_type, file_path, s3_key, metadata, created_at)
VALUES 
    (gen_random_uuid(), 'image', '/assets/diagram1.png', 'diagrams/testamentary-traces-001.png', '{"format": "png", "size_kb": 245}'::jsonb, NOW()),
    (gen_random_uuid(), 'image', '/assets/chart1.png', 'charts/temporal-drift-chart.png', '{"format": "png", "size_kb": 189}'::jsonb, NOW()),
    (gen_random_uuid(), 'image', '/assets/graph1.png', 'graphs/evidence-graph.png', '{"format": "png", "size_kb": 312}'::jsonb, NOW()),
    (gen_random_uuid(), 'pdf', '/docs/research-paper.pdf', 'papers/testamentary-traces-analysis.pdf', '{"format": "pdf", "pages": 24}'::jsonb, NOW()),
    (gen_random_uuid(), 'pdf', '/docs/methodology.pdf', 'papers/research-methodology.pdf', '{"format": "pdf", "pages": 12}'::jsonb, NOW()),
    (gen_random_uuid(), 'image', '/assets/screenshot1.png', 'screenshots/ui-dashboard.png', '{"format": "png", "size_kb": 567}'::jsonb, NOW()),
    (gen_random_uuid(), 'image', '/assets/visualization.png', 'viz/data-visualization.png', '{"format": "png", "size_kb": 423}'::jsonb, NOW());
