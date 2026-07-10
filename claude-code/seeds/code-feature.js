// Seed: code-feature — implement a feature across files: plan, write per-file, self-review.
// Claude Code Workflow edition. args: { spec, files: [{path, content}] }
export const meta = {
  name: 'code-feature',
  description: 'Implement a feature: plan the minimal edits, generate per-file changes, self-review each.',
  phases: [{ title: 'Plan' }, { title: 'Implement' }, { title: 'Review' }],
}

const spec = (args && args.spec) || ''
const files = (args && args.files) || []
const byPath = Object.fromEntries(files.map((f) => [f.path, f.content]))

const PLAN_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['steps'],
  properties: { steps: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['path', 'change'],
    properties: { path: { type: 'string' }, change: { type: 'string' } } } } },
}
const NEW_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['content', 'note'],
  properties: { content: { type: 'string' }, note: { type: 'string' } },
}
const REVIEW_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['approved', 'issues'],
  properties: { approved: { type: 'boolean' }, issues: { type: 'string' } },
}

phase('Plan')
const plan = await agent(
  `Plan the MINIMAL edits to implement this feature:\n${spec}\n\nExisting files:\n` +
  files.map((f) => `- ${f.path}`).join('\n'),
  { label: 'plan', phase: 'Plan', model: 'opus', schema: PLAN_SCHEMA })
const steps = (plan && plan.steps) || []

phase('Implement')
const edits = (await parallel(steps.map((step) => () =>
  agent('Apply this change and return the FULL new file content.\n' +
        `CHANGE: ${step.change}\nFEATURE SPEC: ${spec}\n\nCURRENT (${step.path}):\n${byPath[step.path] || ''}`,
        { label: `impl:${step.path}`, phase: 'Implement', model: 'sonnet', schema: NEW_SCHEMA })
    .then((r) => ({ path: step.path, content: (r && r.content) || '', note: (r && r.note) || '' }))))).filter(Boolean)

phase('Review')
const reviewed = (await parallel(edits.map((e) => () =>
  agent('Review this edit against the spec. Flag bugs/omissions; approve only if correct.\n' +
        `SPEC: ${spec}\nFILE ${e.path}:\n${e.content}`,
        { label: `review:${e.path}`, phase: 'Review', model: 'opus', schema: REVIEW_SCHEMA })
    .then((v) => ({ ...e, approved: !!(v && v.approved), issues: (v && v.issues) || '' }))))).filter(Boolean)

const approved = reviewed.filter((r) => r.approved).length
log(`${approved}/${reviewed.length} edits approved`)
return { edits: reviewed, approved, total: reviewed.length }
