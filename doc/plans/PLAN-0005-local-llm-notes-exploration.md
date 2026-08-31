# Handoff: exploring local LLMs for the notes vault

Written at the end of the session that shipped `notes-similar`
([[PLAN-0004-semantic-similar-notes]]), for a fresh session with no memory of it.

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

- **Tool #2 — cluster-level health in `notes-graph`.** Unstarted, and the reason the
  shared module exists. Primary output was to be **clusters with no hub**. Everything it
  needs is in place: `notes_cluster.shape()`, `components()`, `louvain()`, and a fixture
  (`hubless-one`..`four`) built specifically for it.
- **Whether bridge ranking actually helps**, which only real use can answer. The
  original question — do top hits read as connections worth making, or just shared
  vocabulary? — is now *answerable*, because every row states its cluster and the header
  states the graph the clustering ran on. It is not yet *answered*.
- The embedding-model swap (`bge-m3`) remains unscheduled, not closed.
- `master` is now **6 commits ahead of `origin/master`**, still unpushed.
- `deadlinks.lua`'s unsanitized `rel` field is still unfixed — a known one-line change,
  deferred again. `similar.lua` sanitizes; `deadlinks.lua` does not.
- `bin/mknote` still writes to `~/Sync/notes` while everything else uses `~/notes`.
  Flagged three times now, never resolved.
