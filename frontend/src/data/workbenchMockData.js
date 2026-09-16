export const missingnessMock = {
  completenessCards: [
    { label: 'Metadata completeness', value: '68%', note: 'Title, year, and PID fields are mostly present, but description remains uneven.' },
    { label: 'Retrieval coverage', value: '4/4 PDFs', note: 'Only four Docling-ingested PDFs are available for the current workbench.' },
    { label: 'Entity presence', value: 'Sparse', note: 'Entity-level signals are still too thin for archive-wide conclusions.' },
    { label: 'Institutional gaps', value: '12 flags', note: 'Description and access gaps are being surfaced as analytical objects.' }
  ],
  negativeRetrievalLog: [
    { id: 'neg-1', query: 'Where does the archive document women-led design administration?', outcome: 'No documentary trace returned', note: 'Could reflect absent ingestion or archival silence.' },
    { id: 'neg-2', query: 'Find oral testimony on departmental budgeting decisions', outcome: 'Partial retrieval', note: 'Only indirect references surfaced.' },
    { id: 'neg-3', query: 'Which records connect DDR pedagogy to public sector design?', outcome: 'Sparse metadata', note: 'Candidate records exist but metadata is too thin for confident filtering.' }
  ],
  events: [
    { event_id: 'miss-001', type: 'descriptive', query_or_entity_or_field: 'creator field', evidence: 'Creator missing on two retrieved PDF records', source_document_id: '606', status: 'open', reviewer_note: 'Check synced authority record.', created_at: '2026-06-11T08:10:00Z' },
    { event_id: 'miss-002', type: 'retrieval', query_or_entity_or_field: 'women-led administration', evidence: 'The local model returned no chunks for a targeted source interrogation query.', source_document_id: 'unknown', status: 'reviewing', reviewer_note: 'Treat as provisional absence only.', created_at: '2026-06-11T08:14:00Z' },
    { event_id: 'miss-003', type: 'documentary', query_or_entity_or_field: 'oral-history transcript', evidence: 'Passage reference exists in notes but no transcript source is ingested locally.', source_document_id: 'N/A', status: 'open', reviewer_note: 'Mock passage retained until transcript ingestion exists.', created_at: '2026-06-11T08:20:00Z' },
    { event_id: 'miss-004', type: 'computational', query_or_entity_or_field: 'embedding coverage', evidence: 'One PDF has incomplete downstream embedding metadata.', source_document_id: '602', status: 'triaged', reviewer_note: 'Track before scaling corpus size.', created_at: '2026-06-11T08:26:00Z' },
    { event_id: 'miss-005', type: 'historiographic', query_or_entity_or_field: 'institutional conflict', evidence: 'Archive description foregrounds projects more than contestation.', source_document_id: '599', status: 'open', reviewer_note: 'Surface as a caveat in claims.', created_at: '2026-06-11T08:31:00Z' }
  ]
}

export const crossReadMock = {
  passages: [
    {
      passage_id: 'pass-001',
      passage_text: 'We kept redesigning the course structure because the institution could not decide whether design research was method, history, or administration.',
      speaker_or_source: 'Oral history interview A',
      retrieved_chunk_ids: ['chunk-112', 'chunk-208'],
      relation_type: 'complicates',
      reviewer_note: 'Institutional uncertainty is present, but the record is indirect.',
      confidence_or_status: 'reviewing'
    },
    {
      passage_id: 'pass-002',
      passage_text: 'The archive remembers exhibitions better than the labour that made them possible.',
      speaker_or_source: 'Fieldnote fragment',
      retrieved_chunk_ids: ['chunk-019'],
      relation_type: 'supports',
      reviewer_note: 'Matches current descriptive imbalance in local records.',
      confidence_or_status: 'provisional'
    }
  ],
  candidateChunks: {
    'pass-001': [
      { chunk_id: 'chunk-112', title: 'DDR meeting notes 1979', pid: 'pid_112', excerpt: 'Curriculum discussions remain unresolved across teaching and administration.' },
      { chunk_id: 'chunk-208', title: 'Department memo 1980', pid: 'pid_208', excerpt: 'Design research position continues to be debated internally.' }
    ],
    'pass-002': [
      { chunk_id: 'chunk-019', title: 'Exhibition planning record', pid: 'pid_019', excerpt: 'Public-facing exhibition outputs are documented in more detail than supporting labour.' }
    ]
  }
}

export const claimsMock = [
  {
    claim_id: 'claim-001',
    claim_text: 'DDR administrative records foreground outputs more consistently than they document supporting labour.',
    evidence_chunk_ids: ['chunk-019', 'chunk-208'],
    support_level: 'supported',
    caveats: 'Local corpus contains only four Docling-ingested PDFs.',
    reviewer_status: 'ready-for-supervisor-review',
    created_at: '2026-06-11T08:40:00Z',
    updated_at: '2026-06-11T08:44:00Z'
  },
  {
    claim_id: 'claim-002',
    claim_text: 'Women-led administrative labour is absent from the archive.',
    evidence_chunk_ids: [],
    support_level: 'unresolved',
    caveats: 'Current state may reflect retrieval and ingestion gaps rather than documentary absence.',
    reviewer_status: 'needs-evidence',
    created_at: '2026-06-11T08:45:00Z',
    updated_at: '2026-06-11T08:45:00Z'
  },
  {
    claim_id: 'claim-003',
    claim_text: 'Cross-read probes suggest institutional uncertainty around the status of design research.',
    evidence_chunk_ids: ['chunk-112'],
    support_level: 'partially_supported',
    caveats: 'Needs more archival records before generalising.',
    reviewer_status: 'in-review',
    created_at: '2026-06-11T08:46:00Z',
    updated_at: '2026-06-11T08:47:00Z'
  }
]

export const auditMock = {
  sessions: [
    { id: 'sess-1', timestamp: '2026-06-11 08:23', query: 'Source interrogation retrieval probe on DDR administration', retrieved_chunks: 3, status: 'logged' },
    { id: 'sess-2', timestamp: '2026-06-11 08:31', query: 'Cross-read passage mapping', retrieved_chunks: 2, status: 'mocked' }
  ],
  exports: [
    'Retrieval trail memo (.md / .json)',
    'Absences / missingness report (.csv)',
    'Cross-read testimony-record map (.csv)',
    'Atlas coordinate export (.csv)',
    'Claim-evidence matrix (.csv / .md)'
  ]
}
