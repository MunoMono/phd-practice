import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildScholarlyPresentation, citationTextNodes, consolidateSources,
  exportScholarlyAnswer, normaliseScholarlyProse,
} from '../src/utils/scholarlyPresentation.js'

const trace = () => ({
  answer: 'Original claim [EV-123456789abc, EV-abcdef123456]. Repeated [EV-123456789abc].',
  documentarySpans: [
    { evidence_id: 'EV-123456789abc', document_id: 'doc1', chunk_id: 'c1', page: 0, title: 'Report one', text: 'Original—passage', asset_pid: 'pid1' },
    { evidence_id: 'EV-abcdef123456', document_id: 'doc1', chunk_id: 'c2', page: 2, title: 'Report one', text: 'Another original passage', asset_pid: 'pid1' },
  ],
})

test('citation numbering is stable for repeated passages and multiple references', () => {
  const p = buildScholarlyPresentation(trace())
  assert.deepEqual(p.notes.map((n) => n.number), [1, 2])
  assert.equal(p.resolve('EV-123456789abc').number, 1)
  assert.notEqual(p.notes[0].target, p.notes[1].target)
  assert.deepEqual(p.warnings, [])
})

test('every Unicode hyphen variant resolves without rewriting identifiers', () => {
  for (const hyphen of ['-', '‐', '‑', '‒', '–', '—', '−']) {
    const t = trace()
    t.answer = `Claim [EV${hyphen}123456789abc]. Bare EV${hyphen}123456789abc.`
    const p = buildScholarlyPresentation(t)
    assert.equal(p.notes.length, 1)
    assert.deepEqual(p.warnings, [])
    assert.equal(citationTextNodes(p.text, p).filter((n) => n.type === 'citation').length, 2)
  }
})

test('no space precedes citation; superscript precedes sentence punctuation', () => {
  const p = buildScholarlyPresentation(trace())
  const nodes = citationTextNodes('A claim [EV-123456789abc]. More.', p)
  assert.equal(nodes[0].value, 'A claim')
  assert.equal(nodes[1].data.hName, 'sup')
  assert.equal(nodes[2].value, '.')
  assert.equal(nodes[3].value, ' More.')
  const afterStop = citationTextNodes('A claim. [EV-123456789abc] More.', p)
  assert.equal(afterStop[0].value, 'A claim')
  assert.equal(afterStop[1].type, 'citation')
  assert.equal(afterStop[2].value, '.')
  assert.equal(afterStop[3].value, ' More.')
  assert.equal(citationTextNodes("Archer's formulation [EV-123456789abc] remains.", p)[0].value, "Archer's formulation")
})

test('unresolved or ambiguous references do not fabricate links', () => {
  const t = trace()
  t.answer = 'Unknown [EV-000000000000].'
  const p = buildScholarlyPresentation(t)
  assert.equal(p.notes.length, 0)
  assert.equal(p.warnings.length, 1)
  assert.equal(citationTextNodes(p.text, p)[1].children[0].url, '#citation-warnings')
  t.answer = 'Ambiguous [EV-123456789abc].'
  t.documentarySpans.push({ ...t.documentarySpans[0], chunk_id: 'other', text: 'Different passage.' })
  assert.equal(buildScholarlyPresentation(t).notes.length, 0)
})

test('deduplication preserves distinct passages, pages, aliases and immutable input', () => {
  const t = trace()
  t.sources = [
    { documentId: 'doc1', chunkId: 'c1', page: 0, title: 'Report one', excerpt: 'Original—passage' },
    { documentId: 'doc1', chunkId: 'c1', page: 0, title: 'Report one', excerpt: 'Original—passage' },
    { documentId: 'doc1', chunkId: 'c1', page: 0, title: 'Report one', excerpt: 'Distinct original sentence.' },
  ]
  const saved = JSON.stringify(t)
  const sources = consolidateSources(t)
  assert.equal(sources.length, 3)
  assert.equal(new Set(sources.map((s) => s.anchor)).size, 3)
  assert.deepEqual(sources[0].aliases, ['source-1', 'source-2', 'evidence-EV-123456789abc'])
  assert.equal(sources[0].excerpt, 'Original—passage')
  assert.equal(JSON.stringify(t), saved)
})

test('legacy numeric citations resolve to the actual source-group passage', () => {
  const t = trace()
  t.answer = 'Grouped passage [4].'
  t.sourceGroups = [{ title: 'Grouped report', document_id: 'doc2', chunks: [
    { chunk_id: 'cg', source_number: 4, page_start: 8, text: 'Grouped original.' },
  ] }]
  const p = buildScholarlyPresentation(t)
  assert.equal(p.notes[0].source.chunkId, 'cg')
  assert.equal(p.notes[0].source.page, 8)
})

test('generated prose uses unspaced en dashes but quotations, code, URL and IDs stay original', () => {
  const text = 'Ideas — although disputed — remain. Design—science. 1965–1985.\n'
    + '"Original—quote" ‘Another — quote’ \'Third—quote\'. `doc—123` https://example.org/a—b\n'
    + '> Quotation—unchanged.\n```json\n{"id":"x—y"}\n```\n[EV—123456789abc]'
  const result = normaliseScholarlyProse(text)
  assert.ok(result.startsWith('Ideas–although disputed–remain. Design–science. 1965–1985.'))
  for (const original of ['"Original—quote"', '‘Another — quote’', "'Third—quote'", '`doc—123`', 'https://example.org/a—b', '> Quotation—unchanged.', '{"id":"x—y"}', '[EV—123456789abc]']) {
    assert.ok(result.includes(original), original)
  }
})

test('Markdown export shares citations, punctuation and unresolved warnings with display', () => {
  const t = trace()
  t.answer = 'Interpretation — bounded [EV-123456789abc]. Unknown [EV-000000000000].'
  const exported = exportScholarlyAnswer(t)
  assert.ok(exported.includes('Interpretation–bounded<sup>[1](#source-card-1)</sup>.'))
  assert.ok(exported.includes('<a id="source-card-1"></a>Report one'))
  assert.ok(exported.includes('p. 0'))
  assert.ok(exported.includes('Unresolved citation: EV-000000000000'))
  assert.equal(t.documentarySpans[0].text, 'Original—passage')
})

test('paragraph-structured authority and documentary citations remain distinct', () => {
  const t = trace()
  t.answer = ''
  t.authorityEvidence = [{ authority_id: 'person1', assertion: 'Recorded employment' }]
  t.answerParagraphs = [{ claims: [{ text: 'Claim', source_numbers: [1], authority_numbers: [1] }] }]
  t.sources = [{ documentId: 'doc3', chunkId: 'c3', page: 3, title: 'Document', excerpt: 'Exact passage.' }]
  const p = buildScholarlyPresentation(t)
  assert.deepEqual(p.notes.map((n) => n.target), ['source-card-1', 'authority-1'])
})

test('existing citation links preserve their actual targets instead of inferring from link labels', () => {
  const t = trace()
  t.answer = 'Linked [1](#evidence-EV-abcdef123456). External [1](https://example.org) `EV-123456789abc`.'
  const p = buildScholarlyPresentation(t)
  assert.equal(p.notes.length, 1)
  assert.equal(p.notes[0].source.chunkId, 'c2')
  const exported = exportScholarlyAnswer(t)
  assert.ok(exported.includes('[1](https://example.org)'))
  assert.ok(exported.includes('`EV-123456789abc`'))
})

test('adjacent citation groups share a punctuated superscript without ambiguous joined numbers', () => {
  const p = buildScholarlyPresentation(trace())
  const nodes = citationTextNodes('Bounded [EV-123456789abc] [EV-abcdef123456].', p)
  assert.equal(nodes[0].value, 'Bounded')
  assert.equal(nodes.filter((node) => node.type === 'citation').length, 1)
  assert.deepEqual(nodes[1].children.map((node) => node.value || node.children[0].value), ['1', ',', '2'])
})

test('ambiguous deep links and numeric mappings warn rather than silently selecting a passage', () => {
  const t = trace()
  t.documentarySpans.push({ ...t.documentarySpans[0], chunk_id: 'different', text: 'Distinct evidence.' })
  t.answer = 'Ambiguous [1](#evidence-EV-123456789abc).'
  const p = buildScholarlyPresentation(t)
  assert.equal(p.notes.length, 0)
  assert.ok(p.warnings[0].includes('#evidence-EV-123456789abc'))
  assert.ok(p.sources.every((source) => !source.anchorAliases.includes('evidence-EV-123456789abc')))
  t.answer = 'Ambiguous [4].'
  t.sourceGroups = [{ chunks: [
    { document_id: 'doc2', chunk_id: 'a', source_number: 4, text: 'Passage A.' },
    { document_id: 'doc2', chunk_id: 'b', source_number: 4, text: 'Passage B.' },
  ] }]
  assert.equal(buildScholarlyPresentation(t).notes.length, 0)
})
