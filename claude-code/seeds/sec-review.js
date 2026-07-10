// Seed: sec-review — review a diff across dimensions, adversarially verify each finding.
// Claude Code Workflow edition. args: a diff/code string, or { diff }.
// pipeline: each dimension's findings verify as soon as that dimension is done (no barrier).
export const meta = {
  name: 'sec-review',
  description: 'Find correctness + security issues in a diff, then adversarially verify each finding before reporting.',
  phases: [{ title: 'Review' }, { title: 'Verify' }],
}

const diff = (typeof args === 'string') ? args : (args && args.diff) || ''

const FIND_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['findings'],
  properties: { findings: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['title', 'location', 'detail'],
    properties: { title: { type: 'string' }, location: { type: 'string' }, detail: { type: 'string' } } } } },
}
const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['real', 'why'],
  properties: { real: { type: 'boolean' }, why: { type: 'string' } },
}

const DIMENSIONS = [
  ['correctness', 'logic bugs, edge cases, off-by-one, error handling, nullability'],
  ['security', 'injection, authz, secrets, unsafe deserialization, path traversal, SSRF'],
  ['resource', 'leaks, unbounded growth, blocking I/O on hot paths, races, deadlock'],
]

phase('Review')
const results = await pipeline(DIMENSIONS,
  // stage 1: review one dimension
  async ([key, desc]) => {
    const r = await agent(
      `Review this diff for ${key} issues (${desc}). Be specific and cite locations.\n\nDIFF:\n${diff}`,
      { label: `review:${key}`, phase: 'Review', model: 'sonnet', schema: FIND_SCHEMA })
    return { key, findings: (r && r.findings) || [] }
  },
  // stage 2: adversarially verify this dimension's findings (fires as soon as stage 1 is done)
  async ({ key, findings }) => parallel(findings.map((f) => () =>
    agent(`Adversarially verify this ${key} finding. Try to REFUTE it; set real=false unless it is ` +
          `clearly triggerable/exploitable given the diff.\nTITLE: ${f.title}\nLOCATION: ${f.location}\n` +
          `DETAIL: ${f.detail}\n\nDIFF:\n${diff}`,
          { label: `verify:${key}`, phase: 'Verify', model: 'opus', schema: VERDICT_SCHEMA })
      .then((v) => ({ ...f, dimension: key, verdict: v })))))

const confirmed = results.filter(Boolean).flat().filter((f) => f && f.verdict && f.verdict.real)
log(`${confirmed.length} confirmed findings`)
return { findings: confirmed, count: confirmed.length }
