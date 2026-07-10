// Seed: bug-fix — reproduce, locate root cause, patch, verify.
// Claude Code Workflow edition. args: { report, code, tests? }
export const meta = {
  name: 'bug-fix',
  description: 'Fix a reported bug: reproduce, locate the root cause, patch minimally, verify no regressions.',
  phases: [{ title: 'Reproduce' }, { title: 'Locate' }, { title: 'Fix' }, { title: 'Verify' }],
}

const report = (args && args.report) || ''
const code = (args && args.code) || ''
const tests = (args && args.tests) || ''

const LOC_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['root_cause', 'location'],
  properties: { root_cause: { type: 'string' }, location: { type: 'string' } },
}
const FIX_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['content', 'explanation'],
  properties: { content: { type: 'string' }, explanation: { type: 'string' } },
}
const VERIFY_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['fixed', 'regressions'],
  properties: { fixed: { type: 'boolean' }, regressions: { type: 'string' } },
}

phase('Reproduce')
const repro = await agent(
  `State the exact failing behavior and a minimal reproduction.\nREPORT: ${report}\n\nCODE:\n${code}`,
  { label: 'reproduce', phase: 'Reproduce', model: 'sonnet' })

phase('Locate')
const loc = await agent(
  `Find the ROOT CAUSE (not the symptom).\nREPRO: ${repro}\n\nCODE:\n${code}`,
  { label: 'locate', phase: 'Locate', model: 'opus', schema: LOC_SCHEMA })

phase('Fix')
const fix = await agent(
  'Patch the root cause with the SMALLEST correct change. Return the full new file.\n' +
  `ROOT CAUSE: ${(loc && loc.root_cause) || ''}\n\nCODE:\n${code}`,
  { label: 'fix', phase: 'Fix', model: 'sonnet', schema: FIX_SCHEMA })

phase('Verify')
const testsClause = tests ? `\nCheck against these tests:\n${tests}` : ''
const ver = await agent(
  'Does this patch fix the bug without regressions?' + testsClause + '\n' +
  `REPORT: ${report}\nPATCH:\n${(fix && fix.content) || ''}`,
  { label: 'verify', phase: 'Verify', model: 'opus', schema: VERIFY_SCHEMA })

return {
  root_cause: (loc && loc.root_cause) || '',
  patch: (fix && fix.content) || '',
  explanation: (fix && fix.explanation) || '',
  fixed: !!(ver && ver.fixed),
  regressions: (ver && ver.regressions) || '',
}
