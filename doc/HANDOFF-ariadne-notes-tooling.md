# Handoff: Ariadne notes tooling

**Status as of 2026-09-05.** Written to be read cold. Supersedes the 2026-09-02
handoff, whose work is all shipped.

## Goal

Extend the Ariadne notes-vault tooling in `bin/` (Python CLIs) and
`base/nvim/nvim/lua/plugins/ariadne/` (Neovim front end). This session
implemented `doc/plans/PLAN-0008-chunked-embedding-index.md` and planned
`doc/plans/PLAN-0009-similarity-search-on-a-selection.md`.

## State

**Shipped, reviewed, committed, not pushed.** Four commits ahead of
`origin/master`; a local hook blocks pushing protected branches, so the user
runs `git push` manually.

```
2469745 Plan similarity search on a visual selection
c1e025a Record PLAN-0008's measured outcome
033562b Prefix --search queries for the model
267a198 Chunk long notes into the embedding index
```

Each commit is independently green — all 17 Python suites pass at every one, so
the history bisects.

**Not started:** PLAN-0009. Two questions gate the CLI shape; see below.

## PLAN-0008, as shipped

Notes over 1500 characters are embedded in pieces cut at their own `##`
headings, and a note's vector is the centroid of those. Everything past
`MAX_CHARS` used to be absent from the index entirely. Full tables in the plan.

Three decisions the measurements **changed**, not confirmed — do not relitigate
without new evidence:

- **The plan's own scoring design was wrong.** Max over chunk *pairs* (ColBERT
  MaxSim) loses on wikilink ground truth, because a max over k samples rises
  with k, so a 59-chunk note outscores a one-chunk note against everything
  (background similarity 0.295 vs 0.379). Shipped instead: chunks on the query
  side, one centroid on the document side (`best_chunk_match`).
- **The plan's conditional-chunking hypothesis and its stated fallback were both
  falsified.** Neither removes the wikilink regression on its own.
- **Structure alone does not bound the chunk count.** One real note in
  `obsidianmd/obsidian-help` splits into 163 chunks (~4.7 s query). Capped by
  `MAX_SECTIONS = 32` (pack short sections) and `MAX_CHUNKS = 40` (hard ceiling).

**Do not resurrect** the two synthetic corpora as the deciding evidence: they
prefer the rejected MaxSim design by a wide margin, and that is the provenance
confound PLAN-0008 already flagged — their related notes share literal passages,
which a chunk-pair max finds trivially. `younggulsong/my-wiki` with the author's
own wikilinks is the closer proxy for what `--similar` answers.

### What PLAN-0008 does not deliver

- **Dilution is unfixed.** Case D went .157 → .152 and .170 → .133. A multi-idea
  note scored by its centroid is still averaged. The fix is the document-side
  max that costs more than it gains. `ariadne-graph`'s `[SPLIT]` remains the
  answer.
- **`--duplicates` thresholds predate chunking.** `EMBED_MIN 0.80` /
  `TITLE_MIN 0.85` were calibrated against whole-note truncated vectors. Short
  notes are byte-identical so unaffected; the cosine bar has not been re-checked
  against centroids. Documented in `bin/CLAUDE.md`, not measured.

## Reviews

Three rounds, all findings addressed and mutation-verified. Round 1
(`code-reviewer` + `security-reviewer` in parallel) returned changes-requested:

- **A real bug:** `save_cache` could write an entry `load_cache` always rejects,
  dropping the *whole* cache — so every run would re-embed and re-upload the
  entire vault, for ever, with no diagnostic. No test would have caught it.
- **Six false-green tests**, each passing while the behaviour it named was
  broken. Round 2 (re-review of the fixes) found three more mistakes in the
  fixes themselves. Details in PLAN-0008's "Review, and the final numbers".

Worth carrying: ask reviewers to name the **false-green trap** and prove findings
by mutation. Assertion alone would have missed all nine.

## How to verify

```sh
cd bin && for f in *_test.py; do printf "%-34s " "$f"; python3 "$f" 2>&1 | tail -1; done
# Expect: OK on all 17
```

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/utils_spec.lua"
# Expect: 30 successes, 0 failures
```

End-to-end needs Ollama (`ariadne-embed-setup --check`). Use a
`tempfile`-built vault or `base/nvim/nvim/lua/plugins/ariadne/dev-vault` —
**never** `~/notes`, and never for benchmarking. See `bin/CLAUDE.md` and
auto-memory `never-benchmark-against-the-real-vault`.

## Before the user next uses the tool

Every note's content hash changed, so the first `:AriadneSimilar` or
`:AriadneDuplicates` will report the vault unindexed and ask for
`:AriadneSimilarIndex` — the `--max-refresh` guard working, not a failure.
~4 minutes.

Repeat this caveat to them: `:AriadneSimilarIndex` builds its argv as
`{"ariadne-similar", "--index", vault}` (`similar.lua:107`) and passes **no**
`--exclude`. If a subtree is meant to stay out of the HTTP upload, index from
the shell with the usual flags.

## Open questions — PLAN-0009

Both block code:

1. **Which ranking should a selection use** — crossing-vs-within like
   `--similar`, or grouped by cluster like `--search`? Needs the user.
   PLAN-0007 settled the equivalent question by asking first.
2. **Does the query prefix carry over to a lifted paragraph?** PLAN-0008
   measured `task: search result | query: X` on *title-shaped* queries. A
   measurement is specified in PLAN-0009 §2: ~5 minutes, public corpora, no
   re-index.

Separately, tracked but not blocking: `--duplicates` is exposed on daily notes.
Date-shaped titles defeat the title signal (`2026-09-04` vs `2026-09-05` scores
0.900 against a 0.85 bar), leaving the 0.80 cosine bar as the only gate, which
stub days already reach at 0.787. Cheap mitigation is `--exclude` on the daily
subtree for `--duplicates` runs.

## Benchmark fixtures

Not committed — scratch, by design. The public corpora and synthetic vaults live
under a prior session's scratchpad and **will not survive indefinitely**:
`/private/tmp/claude-501/-Users-pgk-dotfiles/6d3eb92f-.../scratchpad/{corpora,synth}`
(seven public vaults; `synth/build.py` regenerates the synthetic ones). The
benchmark scripts from this session sit beside them in
`.../0b9a06d6-.../scratchpad/` — `bench_shipped.py` is the one to copy forward,
since it imports the real `note_chunks` rather than reimplementing it. Every
script refuses any path outside `scratchpad/corpora` or `scratchpad/synth`.

If they are gone, re-clone the public vaults; do not substitute the real vault.

## Suggested skills

`/done` before claiming anything finished here — it owns the review gate and has
now caught real bugs three sessions running. Check auto-memory before proposing
an LLM-based feature for this vault, or before assuming a `doc/plans/` file on
disk is the whole history (completed ones get deleted; `git log` finds them).

## Next action

Ask the user PLAN-0009 question 1 (ranking mode). It decides the CLI shape, so
nothing else can start.
