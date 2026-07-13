// Seed: research — multi-angle gather, adversarial per-claim fact-check, synthesize.
// Claude Code Workflow edition. args: a question string, or { question }.
export const meta = {
  name: 'research',
  description: 'Answer a research question with fact-checked claims: gather from multiple angles, adversarially verify each claim, then synthesize.',
  phases: [{ title: 'Gather' }, { title: 'Verify' }, { title: 'Synthesize' }],
}

const AGENT_TIMEOUT_MS = 240000  // guard: a hung agent resolves null, never stalls parallel()
const aw = (p, o) => Promise.race([
  agent(p, o),
  new Promise((r) => setTimeout(() => { log(`timeout: ${(o && o.label) || 'agent'}`); r(null) }, AGENT_TIMEOUT_MS)),
])

const question = (typeof args === 'string') ? args : (args && args.question) || ''

const CLAIM_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['claims'],
  properties: { claims: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['claim', 'support'],
    properties: { claim: { type: 'string' }, support: { type: 'string' } } } } },
}
const VERDICT_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['supported', 'why'],
  properties: { supported: { type: 'boolean' }, why: { type: 'string' } },
}

phase('Gather')
const angles = ['core definitions & established facts', 'recent developments & data',
                'counter-evidence, caveats & failure modes']
const gathered = await parallel(angles.map((a) => () =>
  aw(`Research this angle — '${a}' — for the question:\n${question}\n\n` +
        'Return 3-6 concrete factual claims, each with its supporting evidence.',
        { label: `gather:${a.slice(0, 18)}`, phase: 'Gather', model: 'sonnet', schema: CLAIM_SCHEMA })))
const claims = gathered.filter(Boolean).flatMap((g) => g.claims || [])
log(`gathered ${claims.length} claims`)

phase('Verify')
const checked = await parallel(claims.map((c) => () =>
  aw('Adversarially fact-check this claim. Try to REFUTE it; set supported=false if the ' +
        `evidence is weak, dated, or over-generalized.\nCLAIM: ${c.claim}\nSTATED SUPPORT: ${c.support}`,
        { label: 'verify', phase: 'Verify', model: 'opus', schema: VERDICT_SCHEMA })
    .then((v) => ({ ...c, verdict: v }))))
const kept = checked.filter((c) => c && c.verdict && c.verdict.supported)
log(`${kept.length}/${claims.length} claims survived fact-check`)

phase('Synthesize')
const answer = await aw(
  `Write a concise, well-structured answer to:\n${question}\n\n` +
  'Use ONLY these verified claims; do not add unsupported statements:\n' +
  kept.map((c) => `- ${c.claim}`).join('\n'),
  { label: 'synthesize', phase: 'Synthesize', model: 'opus' })

return { question, answer, claims_verified: kept.length, claims_total: claims.length }
