// Seed: data-report — turn tabular data into verified stats + chart specs + narrative.
// Claude Code Workflow edition. args: { data: "<csv/table>", goal: "what to surface" }
// Every statistic is independently recomputed before it is used in the narrative.
export const meta = {
  name: 'data-report',
  description: 'Summarize a dataset into verified stats, chart specs, and a narrative (numbers verified vs raw).',
  phases: [{ title: 'Stats' }, { title: 'Verify' }, { title: 'Narrate' }],
}

const data = (args && args.data) || ''
const goal = (args && args.goal) || 'summarize the key trends'

const STAT_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['stats'],
  properties: { stats: { type: 'array', items: {
    type: 'object', additionalProperties: false, required: ['name', 'value', 'how'],
    properties: { name: { type: 'string' }, value: { type: 'string' }, how: { type: 'string' } } } } },
}
const OK_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['correct', 'fix'],
  properties: { correct: { type: 'boolean' }, fix: { type: 'string' } },
}

phase('Stats')
const s = await agent(
  `Goal: ${goal}\nCompute the key summary statistics from this data. For each, show exactly how ` +
  `it was derived.\n\n${data}`,
  { label: 'stats', phase: 'Stats', model: 'sonnet', schema: STAT_SCHEMA })
const stats = (s && s.stats) || []

phase('Verify')
const checked = await parallel(stats.map((st) => () =>
  agent(`Independently recompute and verify: ${st.name} = ${st.value} (claimed method: ${st.how}).\n\n` +
        `DATA:\n${data}`,
        { label: `verify:${st.name.slice(0, 16)}`, phase: 'Verify', model: 'opus', schema: OK_SCHEMA })
    .then((v) => ({ ...st, ok: !!(v && v.correct), fix: (v && v.fix) || '' }))))
const good = checked.filter((c) => c && c.ok)
log(`${good.length}/${stats.length} stats verified`)

phase('Narrate')
const narrative = await agent(
  `Write a short report for goal '${goal}' using ONLY these verified statistics:\n` +
  good.map((c) => `- ${c.name}: ${c.value}`).join('\n'),
  { label: 'narrate', phase: 'Narrate', model: 'opus' })

const chartSpecs = good.slice(0, 5).map((c) => ({ type: 'bar', metric: c.name, value: c.value }))
return { narrative, stats: good, chart_specs: chartSpecs }
