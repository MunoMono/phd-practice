import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'
import { deriveRuntimeStatus } from '../src/utils/runtimeStatus.js'

test('dashboard renders backend-derived, stage-aware Qwen settings', async () => {
  const source = await readFile(new URL('../src/pages/Dashboard/Dashboard.jsx', import.meta.url), 'utf8')
  assert.match(source, /Context window/)
  assert.match(source, /Final synthesis max output/)
  assert.match(source, /Stage output limits/)
  assert.match(source, /runtimeInfo\.context_window_tokens/)
  assert.match(source, /runtimeInfo\.source_analysis_max_output_tokens/)
  assert.match(source, /runtimeInfo\.cross_source_max_output_tokens/)
  assert.match(source, /runtimeInfo\.final_synthesis_max_output_tokens/)
  assert.match(source, /getRuntimeHealth/)
  assert.match(source, /getRetrievalHealth/)
  assert.match(source, /deriveRuntimeStatus/)
  assert.doesNotMatch(source, /Active runtime max tokens/)
  assert.doesNotMatch(source, />Max output</)
})

test('dashboard runtime state is derived from live backend probes', () => {
  assert.deepEqual(
    deriveRuntimeStatus(
      { status: 'healthy', model_status: 'ready', model_loaded: true },
      { status: 'healthy', database: 'connected' }
    ),
    { label: 'Qwen ready', type: 'green', ready: true }
  )
  assert.deepEqual(
    deriveRuntimeStatus(
      { status: 'inference_unavailable', model_status: 'error', model_loaded: false },
      { status: 'healthy', database: 'connected' }
    ),
    { label: 'Retrieval only', type: 'gray', ready: false }
  )
  assert.deepEqual(
    deriveRuntimeStatus(null, null),
    { label: 'Unavailable', type: 'red', ready: false }
  )
})

test('source interrogation uses the exploratory endpoint and backend runtime identity', async () => {
  const source = await readFile(new URL('../src/pages/EvidenceTracer/EvidenceTracer.jsx', import.meta.url), 'utf8')
  const card = await readFile(new URL('../src/components/evidence/EvidenceSourceCard.jsx', import.meta.url), 'utf8')
  const api = await readFile(new URL('../src/api/experiments.js', import.meta.url), 'utf8')
  assert.match(api, /\/api\/analysis\/interrogate/)
  assert.match(api, /mode: 'exploratory'/)
  assert.match(source, /interrogateExploratory\(query/)
  assert.match(source, /getRuntimeModelInfo/)
  assert.match(source, /runtimeInfo\?\.display_name/)
  assert.match(source, /sourceNominationScore/)
  assert.match(source, /passageEvidenceChannel/)
  assert.match(card, /Why this source\?/) 
  assert.match(card, /Why this passage\?/) 
  assert.match(card, /Source nomination score/)
  assert.match(card, /Passage score/)
  assert.doesNotMatch(source, /interrogateTurin/)
})