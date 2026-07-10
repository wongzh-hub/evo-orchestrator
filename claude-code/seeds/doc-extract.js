// Seed: doc-extract — extract a fixed schema from documents, no silent drops.
// Claude Code Workflow edition. args: { docs: [{id, text}], fields: ["title","date",...] }
export const meta = {
  name: 'doc-extract',
  description: 'Extract structured fields from documents against a fixed schema; report anything that failed.',
  phases: [{ title: 'Extract' }],
}

const docs = (args && args.docs) || []
const fields = (args && args.fields) || ['title', 'date', 'summary']
const schema = {
  type: 'object', additionalProperties: false, required: fields,
  properties: Object.fromEntries(fields.map((f) => [f, { type: 'string' }])),
}

phase('Extract')
const got = await parallel(docs.map((d) => () =>
  agent('Extract exactly these fields. Use "" if a field is genuinely absent — never guess or ' +
        `fabricate:\n${JSON.stringify(fields)}\n\nDOCUMENT:\n${d.text}`,
        { label: `extract:${d.id}`, phase: 'Extract', model: 'sonnet', schema })
    .then((r) => ({ id: d.id, fields: r }))))

const records = got.filter((g) => g && g.fields)
const missing = docs.filter((d, i) => !(got[i] && got[i].fields)).map((d) => d.id)
if (missing.length) log(`WARNING: no extraction for ${JSON.stringify(missing)} (reported, not silently dropped)`)
return { records, missing, extracted: records.length, total: docs.length }
