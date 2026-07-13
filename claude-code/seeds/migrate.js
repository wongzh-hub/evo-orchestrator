// Seed: migrate — migrate a deprecated API across many files: discover, transform, verify.
// Claude Code Workflow edition. args: { old_api, new_api, files: [{path, content}] }
// Per-file pipeline so one bad file never sinks the batch; unaffected files skip cheaply.
export const meta = {
  name: 'migrate',
  description: 'Migrate a deprecated API across files; transform + verify each; tolerate partial failure.',
  phases: [{ title: 'Discover' }, { title: 'Transform' }, { title: 'Verify' }],
}

const AGENT_TIMEOUT_MS = 240000  // guard: a hung agent resolves null, never stalls parallel()
const aw = (p, o) => Promise.race([
  agent(p, o),
  new Promise((r) => setTimeout(() => { log(`timeout: ${(o && o.label) || 'agent'}`); r(null) }, AGENT_TIMEOUT_MS)),
])

const oldApi = (args && args.old_api) || ''
const newApi = (args && args.new_api) || ''
const files = (args && args.files) || []

const SITES_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['uses', 'spans'],
  properties: { uses: { type: 'boolean' }, spans: { type: 'array', items: { type: 'string' } } },
}
const NEW_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['changed', 'content', 'note'],
  properties: { changed: { type: 'boolean' }, content: { type: 'string' }, note: { type: 'string' } },
}
const OK_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['ok', 'why'],
  properties: { ok: { type: 'boolean' }, why: { type: 'string' } },
}

phase('Discover')
const out = await pipeline(files,
  async (f) => {
    const r = await aw(
      `Does this file use \`${oldApi}\`? If so, list the call-site snippets.\n\nFILE ${f.path}:\n${f.content}`,
      { label: `scan:${f.path}`, phase: 'Discover', model: 'haiku', schema: SITES_SCHEMA })
    return { file: f, sites: r }
  },
  async ({ file, sites }) => {
    if (!sites || !sites.uses) return { path: file.path, skipped: true }
    const r = await aw(
      `Migrate \`${oldApi}\` -> \`${newApi}\` in this file. Preserve behavior exactly. ` +
      `Return the FULL new file content.\n\nFILE ${file.path}:\n${file.content}`,
      { label: `xform:${file.path}`, phase: 'Transform', model: 'sonnet', schema: NEW_SCHEMA })
    return { path: file.path, result: r }
  },
  async (prev) => {
    if (prev.skipped) return prev
    const r = prev.result
    if (!r || !r.changed) return { path: prev.path, verified: false, reason: 'no change produced' }
    const v = await aw(
      `Does this migrated file use \`${newApi}\` correctly and preserve the original behavior? ` +
      `Flag any regression.\n\nFILE ${prev.path}:\n${r.content}`,
      { label: `verify:${prev.path}`, phase: 'Verify', model: 'opus', schema: OK_SCHEMA })
    return { path: prev.path, verified: !!(v && v.ok), content: r.content, reason: (v && v.why) || '' }
  })

const migrated = out.filter((o) => o && o.verified)
const skipped = out.filter((o) => o && o.skipped)
const failed = out.filter((o) => o && !o.verified && !o.skipped)
log(`${migrated.length} migrated, ${skipped.length} skipped, ${failed.length} failed`)
return { migrated, skipped: skipped.length, failed }
