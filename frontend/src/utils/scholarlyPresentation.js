const evidenceId = (value) => String(value || '').replace(/[\u2010-\u2015\u2212]/g, '-').toUpperCase()
const referencePattern = /\[((?:EV[-\u2010-\u2015\u2212][0-9a-f]{12}|[AC]?\d+)(?:\s*[,;]\s*(?:EV[-\u2010-\u2015\u2212][0-9a-f]{12}|[AC]?\d+))*)\]|\bEV[-\u2010-\u2015\u2212][0-9a-f]{12}\b/gi
const markdownNonProse = /(```[\s\S]*?(?:```|$)|~~~[\s\S]*?(?:~~~|$)|`[^`]*(?:`|$)|!?\[[^\]\n]*\]\([^)\n]*\))/g

export const answerText = (trace = {}) => {
  const text = trace.answer || ''
  if (!(trace.answerParagraphs || []).length) return trace.capture ? text.replace(/\n\*{0,2}EXACT REGISTERED QUESTION\*{0,2}[\s\S]*$/, '') : text
  return (trace.answerParagraphs || []).map((paragraph) => [
    paragraph.title ? `### ${paragraph.title}` : '',
    (paragraph.claims || []).map((claim) => {
      const sources = claim.sourceNumbers || claim.source_numbers || []
      const authorities = claim.authorityNumbers || claim.authority_numbers || []
      return `${claim.text}${sources.length ? `[${sources.join(', ')}]` : ''}${authorities.length ? `[${authorities.map((number) => `A${number}`).join(', ')}]` : ''}`
    }).join(' ')
  ].filter(Boolean).join('\n\n')).join('\n\n')
}

export const normaliseScholarlyProse = (text = '') => text
  .split(/(```[\s\S]*?(?:```|$)|`[^`]*(?:`|$)|https?:\/\/[^\s]+|"(?:[^"\\]|\\.)*(?:"|$)|(?<!\w)'[^'\n]*'(?!\w)|\u201c[^\u201d]*(?:\u201d|$)|\u2018[^\u2019]*(?:\u2019|$)|^>[^\n]*|\b(?:EV|doc|chunk|successor)[-\u2010-\u2015][A-Za-z0-9_-]+\b)/m)
  .map((part, index) => index % 2 ? part : part
    .replace(/[ \t]*[\u2013\u2014][ \t]*/g, '\u2013'))
  .join('')

const sourceDefaults = {
  retrievalChannels: [], metadataMatches: [], sourceNominationChannels: [],
  archiveNominationReasons: [], catalogueLocation: {}, rightsAccess: {},
}

export const consolidateSources = (trace = {}) => {
  const sources = []
  const add = (source, aliases = []) => {
    // Only identical passages in the same documented location are deduplicated.
    const existing = sources.find((item) => source.documentId && source.chunkId
      && item.documentId === source.documentId && item.chunkId === source.chunkId
      && item.page === source.page && item.excerpt === source.excerpt)
    if (existing) {
      existing.aliases = [...new Set([...existing.aliases, ...aliases])]
      existing.evidenceIds = [...new Set([...existing.evidenceIds, ...(source.evidenceIds || [])])]
      for (const [key, value] of Object.entries(source)) {
        if (existing[key] == null || existing[key] === '') existing[key] = value
      }
      return existing
    }
    const item = { ...sourceDefaults, ...source, aliases, evidenceIds: source.evidenceIds || [], anchor: `source-card-${sources.length + 1}` }
    sources.push(item)
    return item
  }
  ;(trace.sources || []).forEach((source, index) => add(source, [`source-${index + 1}`]))
  const fromDocument = (source, fallback = {}) => ({
    ...fallback,
    title: source.title || source.source_title || fallback.title,
    documentId: source.document_id || fallback.documentId,
    chunkId: source.chunk_id || fallback.chunkId,
    page: source.page ?? source.page_start ?? fallback.page,
    excerpt: source.text || source.excerpt || fallback.excerpt,
    date: source.date || fallback.date,
    pid: source.asset_pid || source.pid || fallback.pid,
    publicUrl: source.source_uri || fallback.publicUrl,
    citation: [
      source.title || source.source_title || fallback.title,
      source.date || fallback.date,
      (source.page ?? source.page_start ?? fallback.page) != null ? `p. ${source.page ?? source.page_start ?? fallback.page}` : null,
      source.asset_pid || source.pid || fallback.pid,
      source.source_uri || fallback.publicUrl,
    ].filter(Boolean).join(', '),
    evidenceIds: source.evidence_id ? [source.evidence_id] : [],
    evidenceType: source.evidence_type || fallback.evidenceType,
    evidenceState: source.evidence_status || fallback.evidenceState,
    evidenceRole: source.evidence_role,
    provenance: {
      ...(fallback.provenance || {}), ...source,
      archive_record_pid: source.archive_record_pid || fallback.provenance?.archive_record_pid,
      attached_media_pid: source.attached_media_pid || fallback.provenance?.attached_media_pid,
    },
    identity: {
      recordPid: source.archive_record_pid || fallback.identity?.recordPid,
      mediaPid: source.attached_media_pid || fallback.identity?.mediaPid,
      assetPid: source.asset_pid || fallback.pid,
    },
  })
  ;(trace.documentarySpans || []).forEach((source) => add(fromDocument(source), source.evidence_id ? [`evidence-${source.evidence_id}`] : []))
  ;(trace.sourceGroups || []).forEach((group) => (group.chunks || []).forEach((chunk) => add(
    fromDocument(chunk, { title: group.title, date: group.date, pid: group.pid, documentId: group.document_id,
      collection: group.collection, presets: group.presets, evidenceTypes: group.evidence_types }),
    [`grouped-source-${chunk.source_number}`],
  )))
  ;[...(trace.documentaryEvidence || []), ...(trace.testimonyEvidence || [])].forEach((source) => {
    if (source.text || source.excerpt) add(fromDocument(source), source.evidence_id ? [`evidence-${source.evidence_id}`] : [])
  })
  ;[trace.comparison?.document_a, trace.comparison?.document_b].filter(Boolean).forEach((document) => {
    (document.evidence || []).forEach((source) => add(fromDocument(source, {
      documentId: document.document_id, title: document.title, pid: document.pid,
    })))
  })
  const aliasCounts = new Map()
  sources.forEach((source) => source.aliases.forEach((alias) => aliasCounts.set(alias, (aliasCounts.get(alias) || 0) + 1)))
  return sources.map((source) => ({ ...source, anchorAliases: source.aliases.filter((alias) => aliasCounts.get(alias) === 1) }))
}

export const buildScholarlyPresentation = (trace = {}) => {
  const sources = consolidateSources(trace)
  const byEvidence = new Map()
  const byNumber = new Map()
  const groupedNumbers = new Set()
  sources.forEach((source) => {
    source.evidenceIds.forEach((id) => {
      const key = evidenceId(id)
      // An identifier pointing to different passages is ambiguous, not resolved by order.
      byEvidence.set(key, byEvidence.has(key) && byEvidence.get(key) !== source ? null : source)
    })
    source.aliases.forEach((alias) => {
      const match = alias.match(/^(?:grouped-)?source-(\d+)$/)
      if (!match) return
      const number = match[1]
      if (alias.startsWith('grouped-')) {
        byNumber.set(number, groupedNumbers.has(number) && byNumber.get(number) !== source ? null : source)
        groupedNumbers.add(number)
      } else if (!byNumber.has(number)) byNumber.set(number, source)
    })
  })
  const references = new Map()
  const canonicalReferences = new Set()
  const notes = []
  const warnings = []
  const resolve = (id) => {
    const key = evidenceId(id)
    if (references.has(key)) return references.get(key)
    const authority = /^A\d+$/.test(key) ? trace.authorityEvidence?.[Number(key.slice(1)) - 1] : null
    const source = key.startsWith('EV-') ? byEvidence.get(key)
      : canonicalReferences.has(key) ? sources[Number(key.slice(1)) - 1] : byNumber.get(key)
    const target = authority ? `authority-${key.slice(1)}` : source?.anchor
    if (!target) {
      warnings.push(`Unresolved citation: ${id}. No unique supplied source mapping is available.`)
      references.set(key, null)
      return null
    }
    let note = notes.find((item) => item.target === target)
    if (!note) {
      note = { number: notes.length + 1, target, source, authority }
      notes.push(note)
    }
    references.set(key, note)
    return note
  }
  const text = normaliseScholarlyProse(answerText(trace)).split(markdownNonProse)
    .map((part, index) => {
      if (!(index % 2)) return part
      const link = part.match(/^\[(?:\d+|EV[-\u2010-\u2015\u2212][0-9a-f]{12}|source[ -]?\d+)\]\(#([^)]+)\)$/i)
      if (!link) return part
      const targets = sources.filter((source) => source.anchor === link[1] || source.aliases.includes(link[1]))
      if (targets.length !== 1) {
        if (!/^(?:evidence-EV[-\u2010-\u2015\u2212][0-9a-f]{12}|(?:grouped-)?source-(?:card-)?\d+)$/i.test(link[1])) return part
        warnings.push(`Unresolved citation link: #${link[1]}. No unique supplied source mapping is available.`)
        references.set('C0', null)
        return '[C0]'
      }
      const key = `C${sources.indexOf(targets[0]) + 1}`
      canonicalReferences.add(key)
      return `[${key}]`
    }).join('')
  // Discover notes in reading order without changing the stored answer or identifiers.
  for (const [index, part] of text.split(markdownNonProse).entries()) {
    if (index % 2) continue
    for (const match of part.matchAll(referencePattern)) {
      for (const id of (match[1] || match[0]).split(/\s*[,;]\s*/)) resolve(id)
    }
  }
  return { text, sources, notes, warnings, resolve }
}

export const citationTextNodes = (text, presentation) => {
  const nodes = []
  let offset = 0
  const matches = [...text.matchAll(referencePattern)]
  for (let position = 0; position < matches.length; position += 1) {
    const match = matches[position]
    let end = match.index + match[0].length
    const ids = (match[1] || match[0]).split(/\s*[,;]\s*/)
    while (matches[position + 1] && /^[ \t]*$/.test(text.slice(end, matches[position + 1].index))) {
      const next = matches[++position]
      ids.push(...(next[1] || next[0]).split(/\s*[,;]\s*/))
      end = next.index + next[0].length
    }
    let before = text.slice(offset, match.index).replace(/[ \t]+$/, '')
    const following = text.slice(end)
    const trailing = before.match(/([.,;:!?]+)([*_]{0,3})$/)
    const trailingPunctuation = trailing?.[1] || ''
    if (trailing) before = before.slice(0, -trailing[0].length).replace(/[ \t]+$/, '') + trailing[2]
    const punctuation = trailingPunctuation ? null : following.match(/^[ \t]*([.,;:!?]+)/)
    nodes.push({ type: 'text', value: before })
    const children = []
    ids.forEach((id, index) => {
      if (index) children.push({ type: 'text', value: ',' })
      const note = presentation.resolve(id)
      children.push(note
        ? { type: 'link', url: `#${note.target}`, children: [{ type: 'text', value: String(note.number) }],
          data: { hProperties: { 'aria-label': `Jump to source ${note.number}` } } }
        : { type: 'link', url: '#citation-warnings', children: [{ type: 'text', value: '?' }],
          data: { hProperties: { 'aria-label': 'Inspect unresolved citation' } } })
    })
    nodes.push({ type: 'citation', data: { hName: 'sup', hProperties: { className: 'tracer__source-citation' } }, children })
    if (trailingPunctuation || punctuation) nodes.push({ type: 'text', value: trailingPunctuation || punctuation[1] })
    offset = end + (punctuation ? punctuation[0].length : 0)
  }
  nodes.push({ type: 'text', value: text.slice(offset) })
  return nodes
}

export const scholarlyRemarkPlugin = (presentation) => () => (tree) => {
  const trimEnd = (node) => {
    if (node?.type === 'text') node.value = node.value.replace(/[ \t]+$/, '')
    else if (node?.children?.length) trimEnd(node.children.at(-1))
  }
  const takePunctuation = (node) => {
    if (node?.type === 'text') {
      const punctuation = node.value.match(/[.,;:!?]+$/)?.[0] || ''
      if (punctuation) node.value = node.value.slice(0, -punctuation.length)
      return punctuation
    }
    if (['emphasis', 'strong', 'delete'].includes(node?.type)) return takePunctuation(node.children.at(-1))
    return ''
  }
  const visit = (node) => {
    if (!node.children || ['link', 'linkReference', 'code', 'inlineCode'].includes(node.type)) return
    const children = []
    for (const child of node.children) {
      if (child.type === 'text') {
        const rendered = citationTextNodes(child.value, presentation)
        if (rendered[1]?.type === 'citation' && rendered[0].value === '') {
          trimEnd(children.at(-1))
          const punctuation = takePunctuation(children.at(-1))
          if (punctuation) rendered.splice(2, 0, { type: 'text', value: punctuation })
        }
        children.push(...rendered)
      } else {
        visit(child)
        children.push(child)
      }
    }
    node.children = children
  }
  visit(tree)
}

export const exportScholarlyAnswer = (trace) => {
  const presentation = buildScholarlyPresentation(trace)
  const render = (part) => citationTextNodes(part, presentation).map((node) => node.type === 'text' ? node.value
    : `<sup>${node.children.map((child) => child.type === 'text' ? child.value : `[${child.children[0].value}](${child.url})`).join('')}</sup>`).join('')
  let text = presentation.text.split(markdownNonProse).map((part, index) => index % 2 ? part : render(part)).join('')
  if (presentation.notes.length) text += '\n\n### Notes\n\n' + presentation.notes.map((note) => (
    `${note.number}. <a id="${note.target}"></a>${note.source
      ? `${note.source.title || 'Untitled source'}, ${note.source.date || 'date unavailable'}, p. ${note.source.page ?? 'unavailable'}${note.source.publicUrl ? ` ([original source](${note.source.publicUrl}))` : ''}.`
      : `${note.authority.assertion || note.authority.title || note.authority.label || note.authority.authority_id} (database authority record).`}`
  )).join('\n')
  if (presentation.warnings.length) text += '\n\n<a id="citation-warnings"></a>### Unresolved citations\n\n' + presentation.warnings.join('\n\n')
  return text
}
