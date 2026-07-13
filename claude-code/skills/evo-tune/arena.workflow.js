export const meta = {
  name: 'evo-arena',
  description: 'Internal evo arena for evo-tune (Claude Code edition): mutate the champion -> pairwise order-swapped design-duel -> carry the winner, R rounds, early-stop when a round fails to dethrone. Returns the evolved challenger script. Parity with the Python evo/arena.py + evo/judge.py duel.',
  phases: [ { title:'Generate' }, { title:'Judge' } ],
}

// ---- inputs via args (champion script + journal tail passed by the evo-tune skill) ----
const A = (typeof args !== 'undefined' && args) ? args : {}
const CHAMP = A.champion || ''
const JT = A.journalTail || ''
const BRIEF = A.brief || ''
const ROUNDS = Number.isInteger(A.rounds) ? A.rounds : 2

if (!CHAMP || CHAMP.length < 20) return { challenger_script: CHAMP, improved: false, trajectory: [], error: 'no champion script passed in args.champion' }

// ---- timeout guard: a hung agent resolves null, never stalls a barrier ----
const AGENT_TIMEOUT_MS = 240000
const aw = (p, o) => Promise.race([
  agent(p, o),
  new Promise(r => setTimeout(() => { log(`timeout: ${(o && o.label) || 'agent'}`); r(null) }, AGENT_TIMEOUT_MS)),
])

const CHEAT = `Claude Code Workflow API (author scripts against THIS):
- Script starts: export const meta={name,description,phases:[{title}]} (PURE literal). Then body with top-level await.
- agent(prompt,{label,phase,schema,model,effort,isolation:'worktree',agentType}) -> Promise; returns a string, or a validated object if a JSON-Schema is given.
- parallel(thunks[]) -> BARRIER (a failed thunk -> null; .filter(Boolean)). pipeline(items,...stages) -> per-item, NO barrier (DEFAULT for multi-stage).
- phase(title); log(msg). NO fs, NO Date.now/Math.random. Concurrency cap ~10.
- Patterns: pipeline-by-default; adversarial verify; timeout-guard every agent; schema for structured returns; no silent caps/truncation; right-size fan-out to the brief.`

const SCRIPT_SCHEMA = { type:'object', additionalProperties:false, properties:{ script:{type:'string'} }, required:['script'] }
const WIN_SCHEMA = { type:'object', additionalProperties:false, properties:{ winner:{type:'string', enum:['A','B']}, reason:{type:'string'} }, required:['winner','reason'] }

// alternating mutation pressure across rounds (mirrors evo/arena.py MUTATE_FOCI)
const FOCI = ['correctness & verification coverage', 'robustness, cost-awareness & partial-failure handling']

async function mutate(script, focus, rnd){
  const r = await aw(
`${CHEAT}
You improve a Claude Code WORKFLOW script (this is the text "weight" being evolved). KEEP it a VALID, runnable Workflow script: it must still start with a pure-literal 'export const meta={...}' and use only the API above. Make ONE meaningful improvement focused on: ${focus}. Right-size, do NOT bloat.
Improve against this rubric: task decomposition; right-sized fan-out; verification/adversarial coverage; timeout/error/partial-failure handling; schema use for structured returns; agent-prompt quality; cost-awareness (cheap models for bulk, strong for verify). Avoid anti-patterns (needless barriers, silent caps, no self-heal, over/under-engineering).
TASK BRIEF: ${BRIEF}
WHAT PAST RUNS LEARNED (journal tail): ${JT || '(none)'}
CURRENT SCRIPT:
${script}
Return ONLY the full improved workflow script as the 'script' field.`,
    { label:`mutate r${rnd} [${focus.slice(0,18)}]`, phase:'Generate', model:'opus', schema:SCRIPT_SCHEMA })
  return r && r.script && r.script.length > 20 ? r.script : null
}

async function judgeDesign(aSrc, bSrc, tag){
  const r = await aw(
`${CHEAT}
Judge multi-agent WORKFLOW DESIGN quality (orchestration STRUCTURE), not prose. Weigh: decomposition; right-sized fan-out; verification/adversarial coverage; timeout/error/partial-failure handling; schema use; agent-prompt quality; cost-awareness. Penalize anti-patterns (needless barriers, silent truncation, no self-heal, over/under-engineering for THIS brief). Longer is NOT better.
TASK BRIEF: ${BRIEF}
--- DESIGN A ---
${aSrc}
--- DESIGN B ---
${bSrc}
Pick the better-designed workflow for this brief. Return winner (A or B) and a one-line reason.`,
    { label:`judge ${tag}`, phase:'Judge', model:'opus', schema:WIN_SCHEMA })
  return r && (r.winner === 'A' || r.winner === 'B') ? r.winner : null
}

// duel: run twice order-swapped to cancel position bias; dethrone only on strict majority (tie -> champion holds)
async function duel(bestSrc, mutantSrc, rnd){
  const [w1, w2] = await parallel([
    () => judgeDesign(bestSrc, mutantSrc, `best|mut r${rnd}`),   // slot A = best,   B = mutant
    () => judgeDesign(mutantSrc, bestSrc, `mut|best r${rnd}`),   // slot A = mutant, B = best
  ])
  let bestVotes = 0, mutVotes = 0
  if (w1 === 'A') bestVotes++; else if (w1 === 'B') mutVotes++
  if (w2 === 'A') mutVotes++; else if (w2 === 'B') bestVotes++
  return { dethroned: mutVotes > bestVotes, votes: `mutant ${mutVotes} : ${bestVotes} champion` }
}

phase('Generate')
let best = CHAMP
const traj = []
for (let rnd = 0; rnd < ROUNDS; rnd++){
  const focus = FOCI[rnd % FOCI.length]
  const mut = await mutate(best, focus, rnd)
  if (!mut){ traj.push({ round: rnd, result: 'mutate_failed' }); log(`round ${rnd}: mutation failed; keeping current best`); break }
  const d = await duel(best, mut, rnd)
  traj.push({ round: rnd, focus, dethroned: d.dethroned, votes: d.votes })
  log(`round ${rnd}: dethroned=${d.dethroned} (${d.votes})`)
  if (d.dethroned) best = mut
  else { log('champion held this round; early-stopping arena'); break }
}
const improved = best !== CHAMP
log(`arena done: improved=${improved} over ${traj.length} round(s)`)
return { challenger_script: best, improved, trajectory: traj }
