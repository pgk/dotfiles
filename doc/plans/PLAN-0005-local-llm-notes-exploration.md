# PLAN-0005 — graph tooling for the notes vault

**Status as of 2026-09-01.** Read this section; everything below it is the
reasoning archive, session by session. The archive is worth reading before
re-opening a closed decision, and worth *not* trusting for facts — the session-1
handoff at the top of it is stale in specific ways, flagged where it starts.

## Goal

Make the private `~/notes` Zettelkasten (~3,037 notes, English + Greek, Neovim +
obsidian.nvim) more navigable, using only what the vault already contains. An
exploration of local LLMs for this concluded **no LLM earns a place here**
(Session 2 below, with the reasoning and the closed-idea list). The work is graph
analysis instead.

## What exists

Four stdlib-only CLI tools in `bin/`, each surfaced through an fzf-lua picker.
**None has a `~/notes` default** — every invocation names the vault, as an
argument or via `$NOTES_VAULT` (`notes_common.require_vault`).

| Tool | Command | Answers |
|---|---|---|
| `notes-graph` | `:ObsidianGraphHealth` `<leader>og` | Orphans, sparse notes, and **clusters with no hub** |
| `notes-graph --since 7d` | `:ObsidianActive [window]` `<leader>oa` | **What have I been working on**, grouped by cluster |
| `notes-deadlinks` | `:ObsidianDeadLinks` `<leader>oD` | Dead wikilinks, with fuzzy candidates |
| `notes-similar` | `:ObsidianSimilar` `<leader>oS` | Semantically similar but unlinked notes, **bridging pairs first** |

Shared modules: `notes_common.py` (walking, links, the vault guard, `--exclude`),
`notes_cluster.py` (graph construction, deterministic Louvain, coverage),
`notes_embed_cache.py` / `notes_embed_client.py`, `notes_similar_report.py`.
Lua lives in `base/nvim/nvim/lua/plugins/obsidian/`.

Only `notes-similar` touches the network, and only a loopback embedding endpoint
unless `--allow-remote-endpoint`.

## Decisions that should not be relitigated

Each has its reasoning in the archive below; the one-line why is here.

- **No local LLM.** The user stopped using tags (*"I find connections more
  important"*), and the remaining jobs sit on the wrong side of the
  surface-vs-meaning line. Session 2 has the closed-idea table — do not
  re-propose from it without new information.
- **Louvain, not label propagation.** It yields a modularity score, and the real
  vault is never measured, so the tools cannot be tuned and must instead report
  the shape they found for the reader to judge. Every view prints that shape.
- **Coverage, not degree dominance, decides "has a hub".** Coverage is
  scale-sensitive, so no separate minimum-cluster-size threshold has to be
  invented. A map of content scores 1.0 at every size.
- **Bridge ranking limits each group separately.** One shared limit made the
  within-cluster side permanently invisible, which defeated the comparison the
  feature exists for. See [[reordering-plus-truncation-is-two-decisions]].
- **Clusters and degrees always come from the whole vault**, never from a filter
  (`--since`, `--exclude`). Scoping the graph would make a note linked from fifty
  older notes look like an orphan. Tested.
- **`--since` switches the report** rather than adding a section: twelve active
  notes would be buried under a thousand sparse rows.

## Hard rules

- **Never read, scan, or point anything at `~/notes`** — not to reproduce a bug,
  not to measure. Use `base/nvim/nvim/lua/plugins/obsidian/dev-vault` (22
  synthetic notes) or a `tempfile` dir. Broken twice historically; see
  `bin/CLAUDE.md` and the plugin's `CLAUDE.md`, and
  [[zsh-no-word-splitting-in-test-loops]].
- **Brief subagents explicitly** — they inherit none of the above.
- Files ≤400 lines, functions ≤50. Nothing in `bin/` currently exceeds either.
- Stdlib only in `bin/`. numpy is not installed.

## Two measured assumptions, to re-measure rather than trust

1. **mtime means "the user edited this."** Measured 2026-09-01: 24 / 29 / 3,037
   notes for 1 day / 7 days / total, so ~1% weekly churn — sync is not stamping
   mtimes. `--since` is worthless if this stops holding.
2. **The wikilink graph is connected enough for clustering to mean anything.**
   Never measured on the real vault by instruction, which is why every view
   prints its component count and modularity as a self-caveat.

## How to verify

```sh
cd ~/dotfiles/bin
for f in *_test.py; do printf "%-34s " "$f"; python3 "$f" 2>&1 | tail -1; done
```

Expect **304 tests across 11 suites, all OK** (25/25/46/33/29/29/33/21/20/17/26).

```sh
cd ~/dotfiles && nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/obsidian/utils_spec.lua"
```

Expect **8 successes, 0 failures**. Smoke test against the fixture, never `~/notes`:

```sh
V="$PWD/base/nvim/nvim/lua/plugins/obsidian/dev-vault"
python3 bin/notes-graph "$V"              # 1 hubless cluster, modularity 0.634
python3 bin/notes-graph "$V" --since 1h   # after `touch`ing a fixture note
```

There is no Makefile target, no linter and no type checker configured — the
suites above are the whole gate.

## State

**Done and reviewed** (code review + security review, findings triaged, fixes
mutation-tested): all four tools, the clustering module, the activity view, the
`--exclude` fix, non-finite embedding rejection, the Lua safety helpers and their
specs, and the obsidian.nvim 4.0 deprecation cleanup.

**Not done:** nothing is in progress. `master` is **many commits ahead of
`origin/master` and unpushed** (check with `git rev-list --count
origin/master..master`) — pushing has never been done in these sessions and is
the user's call. `base/nvim/nvim/lazy-lock.json` is modified, predates this work,
and is deliberately left alone.

`bin/mknote` was **deleted 2026-09-01** — it wrote `TAGS:`-style notes to
`~/Sync/notes`, a path and a format the user had already abandoned. Nothing
referenced it.

## Open questions

- Was the 24-notes-in-one-day mtime reading real work or a bulk touch? The `36h`
  activity view answers it. Still unanswered.
- Do `notes-similar`'s bridging hits read as better connections than the
  within-cluster ones, and are the `[NO HUB]` clusters worth writing a map of
  content for? Never compared side by side. This is now a tuning question, not a
  keep-or-remove one — see below.

## Answered by use, 2026-09-01

The user ran the tools and reported back. These are settled unless the tools
change:

- **Does any of this actually help?** Yes — *"generally it helps"*. The four
  views stay. The plan's earlier standing instruction to delete bridge ranking
  and hubless clusters if they did not earn their place is **discharged**; they
  did.
- **Cross-lingual quality.** Greek/English relatedness is *"ok for now"* in
  practice, so `embeddinggemma` stays. The measurement was never taken and the
  `bge-m3` swap (config plus `--rebuild`, no code) is still the fallback if the
  Greek side ever reads wrong.

## Known gaps, none blocking

- Louvain takes ~9.6s on a pathological 3,035-note vault (average degree 200).
  The pickers pass a 30s timeout, which bounds the freeze rather than removing it.
- `graph.lua` / `activity.lua` row builders (`describe`, `describe_cluster`,
  `header_for`) are module-local and untested; export them to pin their behaviour.
  Three of one review round's four findings were in Lua, where there were no tests.

## Suggested skills for the next session

`/tdd` for new behaviour, `/done` before claiming anything is finished (it owns
the review gate and caught a HIGH severity bug this round), and
`/receiving-code-review` when triaging what the reviewers return — two of their
findings this session were wrong on sub-points and needed checking, not obeying.

## Next action

**Nothing is queued.** The trial period is over and the tools passed, so the
next move is whatever the user names — not a removal pass.

---

# Reasoning archive

# Handoff: exploring local LLMs for the notes vault

Written at the end of the session that shipped `notes-similar`
([[PLAN-0004-semantic-similar-notes]]).

> **Stale — kept for its reasoning, not its facts.** Superseded by the status
> section at the top of this file. Specifically wrong now: `dev-vault` has 22
> notes, not 6; `notes-graph` and `notes-deadlinks` no longer default to
> `~/notes`; the test count is 304, not 160; and the "ideas raised but NOT
> built" list below was resolved in Session 2.

## What the next session is being asked to do

Two things, both exploratory — **no implementation was agreed**:

1. **Explore further ways local Ollama models could aid the notes workflow.**
   Broader than embeddings; the user has now seen embeddings work and wants the
   rest of the space.
2. **Research how Zettelkasten-style note-taking specifically benefits from local
   LLMs.** Web research expected. This is a real Zettelkasten (see below), not a
   generic note pile, so "AI second brain" listicles are mostly noise — look for
   what practitioners actually keep using.

Start with discussion and research, not code — last session's discuss, agree the
shape, then build worked well.

## Machine and runtime (verified, end of session)

| | |
|---|---|
| Hardware | Apple M3, 24 GB RAM |
| Ollama | 0.33.2, server on `localhost:11434` |
| Models pulled | `embeddinggemma:latest` only (621 MB) |
| Python | 3.14.7 (`math.sumprod` available; **numpy is not installed**) |
| Node | **absent** — no `node`/`npm`/`bun` on PATH; user was installing nvm |

Budget note: embeddings cost ~0.5 GB resident. A `gpt-oss-20b`-class model is
~14 GB and a Qwen3 27B ~17.5 GB, so a chat model competes with everything else
on a 24 GB machine. This shaped the last session's "embeddings, not an LLM"
decision and should be re-examined honestly rather than assumed.

## The vault (profiled last session — do not re-scan to confirm)

| | |
|---|---|
| Path | `~/notes` (private) |
| Size | 3,035 notes, 91 MB, ~537k words, ~177 words/note |
| Style | Numbered Zettelkasten: `1001a1`, `50g`, `80b`, plus `00 Dashboard` / `01 Top Of Mind` hubs |
| Languages | English **and Greek** — rules out English-only models |
| Frontmatter | 1,913 of 3,035 have it; **1,122 do not** |
| Editor | Neovim + obsidian.nvim, custom workflow in `base/nvim/nvim/obsidian-workflow.md` |

## Hard rule — read this before running anything

`bin/CLAUDE.md` and `base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` forbid
reading, scanning, or pointing any command at `~/notes` during development. Use
`base/nvim/nvim/lua/plugins/obsidian/dev-vault` (synthetic, 6 notes) or a
`tempfile` dir.

Violated twice historically, most recently **in the session that wrote this
file**: a zsh loop passed `"--index --exclude drafts/*"` as one unsplit word, it
landed as the target positional, and the vault fell back to its `~/notes` default
— 3,035 notes read, nothing uploaded. The fix removed the implicit default
entirely. Two lessons: **zsh does not word-split unquoted `$var`**, and a
"low-risk" default-path finding from a reviewer deserved more weight than it got.

## What already exists

Three CLI tools in `bin/`, all stdlib-only, all surfaced through fzf-lua pickers:

- `notes-graph` — orphan / sparsely-connected notes (`<leader>og`)
- `notes-deadlinks` — dead wikilinks with fuzzy candidates (`<leader>oD`)
- `notes-similar` — **new** — semantically similar but *unlinked* notes
  (`<leader>oS`; `<C-y>` inserts the link). Supporting modules
  `notes_embed_cache.py` and `notes_embed_client.py`.

`notes-similar` is built and the real vault **is indexed**: 3,035 notes, 768
dims, 9.3 MB, cache at `~/.cache/notes-similar/<hash>/` mode `0700`/`0600`.
User's verdict after first use: *"seems to work ok"*. 160 tests across 6 suites.

Its design constraints, which any sibling tool should probably inherit: no
implicit vault default (`$NOTES_VAULT` or an argument), loopback-only embedding
endpoint unless `--allow-remote-endpoint`, an egress announcement before any
upload, and graceful degradation to an empty result when no server is running.

## Ideas raised last session but NOT built

From the opening discussion; the user picked `notes-similar` first and these were
left. They are candidates, not commitments — re-litigate freely.

- **Relevance-based daily review.** `:ObsidianDailyReview` currently injects 5
  **random** notes. Embedding `01 Top Of Mind` and pulling nearest neighbours
  would make review track current thinking. Cheap: the index already exists.
- **Frontmatter backfill for the 1,122 notes without it.** The one job where a
  generative model clearly beats embeddings, and a one-time batch, so slow is
  fine. Must write proposals to a review file, never auto-apply. Related: tag
  hygiene — `00 Dashboard` has a duplicated `Note` tag, so there is likely more.
- **Voice capture.** Parakeet-TDT v3 on Apple Silicon is roughly 6× faster than
  Whisper Large v3. Only worth it if the user captures away from the keyboard —
  **this was never confirmed, ask before designing around it.**
- **Chat-with-your-vault RAG.** Actively deprioritized last session and the user
  did not push back: they have 3,000 atomic notes they wrote themselves and a
  working graph, so retrieval is the value and a chat wrapper mostly adds
  hallucination surface. Revisit only with a reason.

## Open questions to put to the user

- **Cross-lingual quality is unverified.** `embeddinggemma` was chosen because
  it is multilingual, but ranking was only ever tested on six synthetic English
  notes. Whether Greek and English notes place sensibly *relative to each other*
  is unknown. Ask what the first week of `<leader>oS` looked like — if
  cross-language hits are noise, that is a model swap (`NOTES_EMBED_MODEL` +
  `--rebuild`), not a code change.
- **Do the top hits read as connections worth making, or just shared vocabulary?**
  This is the question that decides whether to build more of this kind of thing.
- `bin/mknote` writes to `~/Sync/notes`, while obsidian.nvim and all three CLI
  tools use `~/notes`. Flagged twice, never resolved — probably stale.

## Loose ends in the repo

- `master` is **2 commits ahead of `origin/master`** — not pushed.
- Local branch `notes-similar` is merged and can be deleted.
- `base/nvim/nvim/lazy-lock.json` was modified *before* that session and is still
  unstaged. Not ours; left alone deliberately.
- `deadlinks.lua` has the same unsanitized `rel` field that was fixed in
  `similar.lua` — a known one-line fix, deliberately deferred.
- Opening any markdown buffer errors with
  `Error running markdownlint-cli2: ENOENT`. Cause: LazyVim's
  `lazyvim.plugins.extras.lang.markdown` extra wires `markdownlint-cli2` into
  `nvim-lint`, and it is an npm package with no Node runtime installed. Fix after
  nvm: `npm install -g markdownlint-cli2` or `:MasonInstall markdownlint-cli2`.
  Pre-existing and unrelated to the notes tooling.

---

# Session 2 outcome (2026-08-31): the answer is "no LLM"

The exploration above ran. Both questions were researched. **The conclusion is that
no local LLM earns a place in this workflow right now** — the strongest ideas turned
out to be graph work on data the vault already contains. What follows is the reasoning,
so nobody re-opens it from scratch.

## What the user decided

- **Tags are out.** *"I am not using tags anymore, I find connections more important."*
  This alone kills the frontmatter/tag backfill idea, which was the leading LLM
  candidate for most of the session.
- **`01 Top Of Mind` is not what the handoff above assumed.** The relevance-based daily
  review idea was built on a wrong guess about that note's contents. Dropped, unbuilt.
  Don't infer what a note holds from its title.
- **Never point anything at `~/notes` — including for measurement.** Develop against
  synthetic fixtures and grow them as needed. This extends the existing rule: it now
  also rules out "just run it once on the real vault to get numbers."

## Research findings that drove the conclusion

**Luhmann's keyword index was deliberately sparse.** ~1,250 entries for his first
Zettelkasten; ~3,200 keywords for the ~67,000 notes of the second — about one index
entry per twenty notes. He indexed only what he judged "significant," and the index
"made no claims to completeness, but only named the relevant entry points." Tags are an
*entry-point* mechanism, not a description mechanism. Backfilling them to uniform
coverage inverts their function — an index that covers everything discriminates
nothing. (Counts are from secondary sources; the Luhmann archive page would not load.)

**The PKM tooling community demonstrates the failure mode.** LLM auto-taggers produce
tag explosion — the same concept landing as `#interview` / `#field-interview` /
`#source-interview`. The community's own fix is to constrain the model to tags already
in the vault. Moot here now, but worth knowing if tags ever come back.

**Where small LLMs fail is a sharp, well-documented line.** Matuschak, on generated
spaced-repetition prompts: they "reinforce the surface — what is said, rather than what
it *means* or why it matters." The A-MEM critique independently doubts that a small
model can separate "genuine conceptual relationships from surface-level similarity."
Same boundary, two communities, different words. **Deciding whether two notes belong
linked sits on the wrong side of it.**

**"Form vs. content" is the wrong safety test.** zettelkasten.de's Sascha reported two
client case studies: tag generation was *"genuinely value creating with little side
effects"*; proofreading **failed** — grammar fixes of one or two words "fundamentally
altered the intended meaning." Proofreading is maximally "form, not content," and it is
the one that corrupted notes. The real test is a pair: is the task **surface-
determinable**, and is a wrong answer **cheap to spot and reverse**. A bad tag is
visible in a list; a distorted sentence is invisible and permanent.

**The pain practitioners report at this vault's scale wants no LLM.** From the
Zettelkasten forum: *"You cannot check every note for relevancy anymore when you have
1000 of them"* (this vault has 3,035). What they report working: structural layers and
hub notes; carefully chosen titles as the primary contact point; browsing over search,
because search needs you to already know the term. Sascha manages 13,700 notes this way.

**Graph theory answers the open question better than a model does.** Burt's structural
holes: value sits in connections that bridge otherwise-disconnected clusters. Ranking
similar-but-unlinked pairs by whether they *cross* clusters asks whether a link would be
structurally novel — a question topology can answer honestly, without judging meaning.

## Ideas closed (do not re-propose without new information)

| Idea | Why it's closed |
|---|---|
| Frontmatter / tag backfill (1,122 notes) | User doesn't use tags; Luhmann-index reasoning says uniform coverage is anti-purpose anyway |
| Typo / grammar hygiene via LLM | Sascha's documented failure case — subtle meaning distortion, invisible and permanent |
| LLM reranker over `notes-similar` hits | Wrong side of the surface/meaning line; also Ollama has no rerank endpoint (`/api/rerank` → 404 on 0.33.2; upstream issue #4360) |
| LLM note splitting into atomic notes | Requires knowing where one idea ends — not surface-determinable |
| Relevance-based daily review off `01 Top Of Mind` | Built on a wrong assumption about that note |
| Cross-language Greek/English aliases | Survived the LLM cull on merit, then dropped when the list narrowed to graph work. The only LLM idea that passed both safety tests — revisit only if Greek/English notes on one concept are demonstrably failing to link |
| Chat-with-your-vault RAG | Deprioritized in session 1, and the research strengthens that |
| Voice capture (Parakeet-TDT) | Still never confirmed the user captures away from keyboard |

Embedding-model swap (`bge-m3` in place of `embeddinggemma`) is **not** closed, just not
scheduled. A Greek retrieval evaluation (arXiv 2607.21274, 13 models) found multilingual
models beat Greek-specific ones decisively, with bge-m3 at 0.559 nDCG@9 — but
`embeddinggemma` was not among the models tested, so its Greek quality remains unmeasured.
Config change plus `--rebuild`, no code.

## What to build

Two tools, chosen by the user. **They share one core**, which is why they're cheaper
together: `notes-graph`'s existing `build_graph()` already returns exactly the
undirected adjacency map (`neighbors` sets) that community detection consumes.

**1. Cluster-aware `notes-similar`** — extend the existing tool, don't add a new one.
Semantically-similar-but-unlinked pairs gain a cluster column and bridge-weighted
ranking: pairs that join *different* clusters rank above pairs already sitting in the
same neighbourhood, where a link adds little. Reuses the existing 9.3 MB embedding
index unchanged. Directly attacks the standing question of whether top hits are real
connections or shared vocabulary.

**2. Cluster-level health in `notes-graph`** — extend that tool too. Node-level health
(orphans, sparse) already exists; this adds the layer above it. Primary output:
**clusters with no hub** — a group of notes that clearly belong together with no entry
point into them. That is an actionable "write a map of content here," rather than a
centrality score needing interpretation.

### Design decisions (made, not yet validated)

- **A shared clustering module**, alongside `notes_common.py` / `notes_embed_*.py`.
  `build_graph()` moves out of `notes-graph` into shared code so both tools use one
  implementation.
- **Deterministic clustering.** Label propagation and Louvain are both order-dependent.
  Sort by path so reruns produce identical output — a tool that reshuffles its answer
  each run can't show whether the vault is improving. Stdlib-only, so the algorithm is
  hand-written: label propagation is ~30 lines, Louvain ~120 with better quality.
- **Both tools stay read-only** and inherit `notes-similar`'s constraints: no implicit
  vault default, graceful degradation, no network egress beyond the existing embedding
  endpoint.

### Fixtures — this is now blocking work

`dev-vault/` has six English notes with no frontmatter and a link structure built for
orphan- and dead-link-testing. **Six notes cannot exercise community detection at all.**
It needs to grow, per the user's explicit instruction to use synthetic notes and add to
them, with fixtures for: two or more distinct link communities; a bridge note joining
them; a cluster with no hub; a disconnected component. `dev-vault/CLAUDE.md` documents
"six files" and forbids adding files — that rule's stated rationale is that non-note
files skew tool output, so **more synthetic notes are in keeping with it, but the file
must be updated** to describe the expanded fixture set.

### The unknown that stays unknown

Community detection is only meaningful if the real wikilink graph is reasonably
connected. If `~/notes` is actually hundreds of small fragments, #1 degenerates (nearly
every pair crosses a boundary) and #2's "cluster with no hub" becomes noise. The
originally-proposed step 0 was to measure component structure on the real vault — **the
user has ruled that out.**

Consequence: **design defensively rather than tuning to measured numbers.** Both tools
should report the graph shape they actually found (component count, size distribution)
alongside their results, so the output carries its own caveat and the user can judge
whether the clustering meant anything. The user can run that themselves whenever they
want; it must not be a prerequisite.

## Safety gap found while reading the code

The handoff above states the accidental-vault-scan fix "removed the implicit default
entirely." **That is only true of `notes-similar`.** Both `bin/notes-graph:99` and
`bin/notes-deadlinks:92` still carry `default="~/notes"` on the vault positional — the
exact pattern behind the original incident. Given the user's instruction never to point
anything at the real vault, this should be removed from both before the work above lands.

## Still open for the user

- Whether to fix the two `~/notes` defaults as part of this work or separately.
- Which clustering algorithm — label propagation (simpler, ~30 lines) or Louvain
  (better communities, ~120 lines) — given the 400-line file limit.

---

# Session 3 outcome (2026-08-31): tool #1 built

Both open questions were answered by the user: **Louvain**, and **fix the two `~/notes`
defaults first, as their own commit**. Scope was set at fixtures + shared module +
cluster-aware `notes-similar`; cluster-level health in `notes-graph` (tool #2) was
deliberately left for a follow-up.

## What shipped

Four commits on `master`, on top of `d3dcad9`:

| Commit | What |
|---|---|
| `8a5fe39` | Drop the `~/notes` default from every notes tool |
| `f354a25` | Grow dev-vault to cover community detection |
| `27a21b8` | Add deterministic Louvain community detection |
| `b7cac46` | Rank cluster-crossing similar notes first |

New files: `bin/notes_cluster.py` (235 lines), `bin/notes_cluster_test.py`,
`bin/notes_similar_report.py`. 232 tests across 8 suites, all passing.

## Decisions taken during the build

- **`require_vault()` lives in `notes_common.py`.** All three tools share it, so a
  fourth inherits the guard rather than re-deriving it. `bin/CLAUDE.md` was rewritten:
  it used to document the two-tier situation ("`notes-similar` has no default, unlike
  its two siblings") and that distinction no longer exists.
- **`build_graph()` moved to `notes_cluster.py`**, with `adjacency_from_links()`
  alongside it for callers that have already read the notes. `notes-similar` uses the
  latter — it holds every note's links in memory from `scan_vault()`, so re-reading
  3,035 files just to cluster them would have doubled its I/O.
- **`notes_similar_report.py` was extracted** when `notes-similar` hit 398 lines
  against the 400-line limit. Rendering was the natural seam; it left the tool at 338.

## The ranking design, and why it changed mid-build

The plan specified "bridge-weighted ranking". Built as a **hard partition** — cross-
cluster pairs above same-cluster ones — rather than a weighted blend, because a weight
would be a number tuned against a vault nobody is allowed to measure.

The dev-vault smoke test then showed what that costs. Querying `hubless-one`, the best
match by far (`hubless-three`, 0.6796) sits in the target's own cluster, so it was
pushed below twelve cross-cluster hits scoring 0.39–0.53 and vanished off the end of
`-n 10` entirely. On 3,035 notes this gets worse, not better: the cross-cluster pool is
so much larger that within-cluster hits would essentially never appear.

That defeats the whole point — the standing question is *whether top hits are real
connections or shared vocabulary*, and you cannot judge that if one side is never shown.

**Resolution (user's choice): `--limit` applies to each group separately.** Up to N
bridging hits and up to N within-cluster hits, under their own headings. Both sides
always visible, no tuned weight anywhere. `--no-bridge` still gives pure similarity
order under one shared limit.

**Generalisable lesson:** a ranking rule that reorders and *truncates* is two decisions,
not one. The reordering was right; applying one shared limit across the partition was
the bug, and it was invisible until the tool was run on real-ish data.

## dev-vault, and a defect it exposed

Grown 6 → 18 notes: three link communities, `bridge-note` as the sole articulation
point between them, a hubless ring, and a three-note disconnected component. Louvain
recovers exactly that structure, modularity 0.630.

Every note also got **distinctive prose**. All six original notes led with the same
line — *"Synthetic fixture note. Placeholder text only."* — which made every preview
identical and inflated similarity between unrelated fixtures (`orphan-note` was the top
hit for `hub-note` purely on shared filler). A link-only fixture gets away with that; a
fixture backing a *semantic* tool does not. Link sets were verified byte-identical
before and after.

`dev-vault`'s section in `base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` now documents
the cluster-level cases and says explicitly that **more synthetic notes are expected**,
with the constraint that new notes must not disturb the documented degrees of existing
fixtures (an inbound link to `hub-note` is safe; one to a note documented as sparse is
not).

## Still open

- ~~**Tool #2 — cluster-level health in `notes-graph`.**~~ **Built** (`bc6ce2d`), see
  below.
- **Whether bridge ranking actually helps**, which only real use can answer. The
  original question — do top hits read as connections worth making, or just shared
  vocabulary? — is now *answerable*, because every row states its cluster and the header
  states the graph the clustering ran on. It is not yet *answered*.
- The embedding-model swap (`bge-m3`) remains unscheduled, not closed.
- `master` is now **6 commits ahead of `origin/master`**, still unpushed.
- **Pre-existing findings raised by the review of this work, deliberately not fixed**
  (all outside the scope of the clustering task; none introduced by it):
  - `--exclude` matches only whole relative paths, case-sensitively. `--exclude
    journal` or `--exclude Personal/*` silently excludes *nothing*, with no warning.
    This is the one that matters: `--exclude` is the only mechanism keeping a subtree
    out of `notes-similar`'s HTTP upload. Fixing it means deciding whether a bare
    directory name should exclude its tree and whether matching should be
    case-insensitive on APFS — a semantic choice, hence left to the user.
  - `graph.lua` has no `sanitize()` at all, so a note filename containing a newline
    splits one `:ObsidianGraphHealth` picker row in two and mismatches
    `path_by_line`. Same class as the `deadlinks.lua` issue below; `similar.lua` has
    the fix to copy.
  - `deadlinks.lua`'s unsanitized `rel` field — a known one-line change, deferred for
    the third time.
  - `json.loads` accepts `NaN`/`Infinity`, and `normalize()` propagates them, so a
    malfunctioning embedding server writes NaN vectors into
    `~/.cache/notes-similar/` where they persist until `--rebuild` and make every
    score `NaN`. Fix: reject non-finite values in `notes_embed_cache.normalize`.
- `bin/mknote` still writes to `~/Sync/notes` while everything else uses `~/notes`.
  Flagged three times now, never resolved.

---

# Session 4 outcome (2026-09-01): tool #2 built

`notes-graph` now reports **clusters with no hub** alongside its per-note health.
Commit `bc6ce2d`. 258 tests across 7 suites.

## The metric, and why it is coverage rather than degree dominance

"Which clusters have no hub" needs a threshold, and the vault may never be measured
to tune one. Two candidates were tested against planted fixtures:

- **Degree dominance** — is the top note's degree an outlier against its cluster
  peers? Scale-free, but it false-positives on a three-note triangle, so it needs a
  *second* threshold (a minimum cluster size) to be usable.
- **Coverage** — the share of a cluster's other notes reachable in one hop from its
  best-connected member. **Chosen.** A map of content links to everything it indexes,
  so it scores 1.0; and the measure is scale-sensitive, so no minimum-size threshold
  has to be invented.

Measured, planted-fixture behaviour:

| shape | coverage |
|---|---|
| planted MOC, 10 / 20 / 40 notes | 1.0, 1.0, 1.0 |
| hubless mesh, 20 notes | 0.6 – 0.75 |
| hubless mesh, 40 notes | 0.43 – 0.57 |
| hubless mesh, 60 notes | 0.25 – 0.4 |
| any cluster of 2–4 notes | 0.67 – 1.0 |

A MOC scores 1.0 at every size, so `--hub-reach 0.5` has a wide margin and small
clusters can never be flagged. Note Louvain splits a large MOC cluster into the MOC
plus satellite pairs — every resulting piece still scores 1.0, so this produces no
false positives.

## The structural finding that forced the fixture to grow

**A hubless *cluster* cannot be smaller than six notes.** For Louvain to keep a group
whole it must be dense enough that no bipartition improves modularity, and below six
that density forces some note to reach half the group. Exhaustive over every connected
graph, the minimum achievable coverage is 1.0 at n≤3, 0.667 at n=4, exactly 0.5 at n=5
and 0.4 at n=6 — so six is the first reportable size, and the n=5 case is spared only
because the threshold test is `coverage >= min_coverage`. That `>=` is load-bearing;
there is now a test pinning it.

**A correction.** `bc6ce2d`'s commit message says a search over 4,000 random graphs
found no counterexample "under fourteen nodes". That is wrong — it measured *whole
vault* size, not cluster size, and hubless clusters occur there from about n=10 at
roughly 1 in 3,000, which a 4,000-graph search misses three times in four. The
commit's own test fixture, a 10-note `ring_beside_a_clique(6, 4)`, is a counterexample
to its own message. Cluster size is the real bound; vault size is not bounded at all.

Consequences, both worth keeping in mind:

- The `hubless-*` ring grew from 4 notes to **8**. At 4 it scored 0.667 and could never
  have been reported — the fixture was named for a case it did not exercise. Six would
  have sufficed; eight was kept for the three reasons in `dev-vault`'s CLAUDE.md
  section. A *bare* ring of 8 splits into two arcs, so both `dev-vault` and the
  unit-test helper embed it beside a denser cluster.
- This is a *property of the tool*, not a limitation: small clusters genuinely do not
  need a map of content. But it means **the tool cannot be exercised on a toy graph**,
  and anyone shrinking the ring will silently disarm the fixture. `dev-vault`'s
  CLAUDE.md section says so explicitly.

## The security finding the review turned up (`5b6a5a4`)

`vim.cmd("edit " .. vim.fn.fnameescape(path))` — the pattern in every picker in this
directory — **executes a note's filename as Ex commands** if it contains a newline.
`fnameescape` does not escape one, and `nvim_exec2` splits on it first. Confirmed:
the text after the newline came back as `line 2: E492: Not an editor command`. A note
named `a\nso/tmp/payload.md`, arriving via sync or a cloned vault, would appear as an
ordinary orphan row and run arbitrary Vimscript on one `<CR>`. All four pickers now
use `vim.cmd.edit({ args = { path } })`, which is verified to keep the newline literal.

`sanitize()` had to change too, and the reason generalises: **collapsing every control
character to a space is not sanitisation, it is a collision.** `a<TAB>b` and `a b`
rendered identically, and since `path_by_line` is keyed on the rendered row, selecting
one opened the other — the exact failure the helper existed to prevent. It now escapes
(`<09>`) rather than blanks, which is injective, and covers the bidi/zero-width
characters Lua's ASCII-only `%c` misses. One copy in `utils.lua` for all three pickers;
`deadlinks.lua`'s raw `rel` field, deferred three times, went in with it.

## Still open

- **Whether either tool actually helps**, which only real use answers. Both now state
  the graph they ran on (components, clusters, modularity) so their output carries its
  own caveat.
All four of the previous round's open items are closed (`1a31d42`):

- **`--exclude` now matches directory names and is case-insensitive**, and warns when
  a pattern matches nothing. It previously matched only whole relative paths, case
  sensitively, so `--exclude journal` and `--exclude Journal/*` each silently excluded
  nothing — on the tool whose `--exclude` is the only thing keeping a subtree out of
  an HTTP upload. Excluded directories are now pruned from the walk, not filtered
  after it, so their contents are never read. **This is a behaviour change:** a
  pattern that used to match nothing may now exclude notes.
- **Non-finite embeddings are refused** at both the parse (`parse_constant`) and the
  normalise step. `sqrt(nan)` is not 0, so a NaN slipped past the zero-norm guard into
  the cache and made every later score `NaN` until `--rebuild`.
- **`utils_spec.lua`** covers `sanitize` and `edit` with eight plenary specs; reverting
  either helper to its old form fails three. The picker row builders are still
  module-local and untested.
- **No file in `bin/` is over the 400-line limit.** The notes-similar suite is split
  three ways over a shared `notes_similar_testkit.py`.

---

# Session 5 outcome (2026-09-01): a third view, and housekeeping

## The recent-activity view (`eb6efb1`)

`notes-graph --since 7d`, surfaced as `:ObsidianActive [window]` on `<leader>oa`.
Notes touched in a window, grouped by link community, communities ranked by how many
of their notes were touched, and a separate section for touched notes that still have
no links at all.

This came from the user asking, unprompted, how they might "view the most connected
notes I recently touched". Worth recording as a direction, not just a feature:

- **The first two tools are audits** — whole vault, run occasionally, "what is
  structurally wrong". This one is a **daily view** — "what have I been working on".
  Same graph, same clustering, different cadence. The user explicitly ruled out
  historical tracking ("no need to track historically"), which removed the whole
  snapshot/state-file branch and made it a pure filter.
- **Clusters are the unit, not notes.** A flat list of 29 filenames does not answer
  "what was I working on"; `12 of 86 notes touched` does. This is the first thing the
  clustering earned beyond the hubless check.
- **The invariant that matters:** the graph and its clusters are built over the whole
  vault and only the *report* is filtered. Scoping the scan to the window would make
  a note linked from fifty older notes look like an orphan. There is a test pinning
  exactly that.
- `Touched and still orphaned` is the section expected to earn its place daily.

**The assumption underneath it was measured before building**, per the lesson from
`01 Top Of Mind`. mtime has to mean "the user edited this"; the user ran
`find ~/notes -name '*.md' -mtime -N | wc -l` and reported 24 / 29 / 3,037 for
1 day / 7 days / total. About 1% weekly churn, so sync is not stamping mtimes and the
feature is viable. **If that ever stops holding the feature is worthless** — re-measure
before building anything else on it. Noted in the plugin's CLAUDE.md too.

One open observation: 24 of the 29 were touched within a single day. Either a real
burst of work or something bulk-touched them; the 36h view will show which.

## obsidian.nvim deprecations (`2c5c7d2`)

Three warnings on every startup, all from obsidian.nvim's 4.0 migration.
`completion.nvim_cmp` / `completion.blink` are gone — completion now comes from the
built-in `obsidian-ls` LSP, which starts itself — so the whole `completion` block was
removed.

`legacy_commands = false` was the involved one, and the useful distinction is worth
keeping: **eleven of this config's fifteen `Obsidian*` commands are its own**, created
with `nvim_create_user_command`, and are unaffected by the plugin's deprecation. Only
four belonged to obsidian.nvim and moved to `Obsidian <subcommand>`: `search`, `new`,
`backlinks`, `links`. Verified by loading headless and asserting every command still
resolves while `:ObsidianSearch` no longer does.

Two incidental findings: `ObsidianRename` was defined by both the plugin and
`commands.lua` (ours won, because our modules run after `setup()`; the ambiguity is
now gone), and the workflow doc listed `:ObsidianToday` for `<leader>od`, which has
always run our own `:ObsidianDaily` — merely wrong before, and after this change it
would have documented a command that does not exist.

## Still open

- **Whether any of the three views actually helps.** Only real use answers it. All
  three now state the graph they ran on, so their output carries its own caveat.
- Whether the 24-in-a-day mtime burst was real work or a bulk touch.
- Louvain takes 9.6s on a pathological 3,035-note vault (average degree 200); the
  pickers pass a 30s timeout, which bounds the freeze rather than removing it.
- `graph.lua`'s `describe`, `describe_cluster` and `header_for` are module-local and
  untested; export them if their behaviour needs pinning. `activity.lua`'s `describe`
  is in the same position.
- `deadlinks.lua` still renders through the shared `sanitize`, but nothing else in it
  is tested.
- Embedding-model swap (`bge-m3`) still unscheduled, not closed.
- `master` is **18 commits ahead of `origin/master`** before this plan update,
  unpushed. Pushing is the user's call and has never been done in these sessions.
