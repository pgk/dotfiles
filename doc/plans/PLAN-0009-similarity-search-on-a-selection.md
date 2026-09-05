# Similarity search on a visual selection

## Context

`:AriadneSimilar` compares against a *whole note*. That is the wrong unit
whenever the note is not about one thing, and it is actively misleading for
notes carrying boilerplate: every daily note in this vault opens with
`Previous #daily-note was: [[…]]`, and that one line is a large fraction of a
short note.

Measured on synthetic daily-note-shaped notes (public/synthetic only, real
vault untouched) — the shared opening line lifts pairwise cosine by a flat
+0.09 to +0.12:

| body length | mean cosine without | with the opening line |
| --- | --- | --- |
| stub (~8 ch) | 0.636 | 0.723 (max 0.787) |
| medium (~55 ch) | 0.459 | 0.559 |
| long (~120 ch) | 0.378 | 0.502 |

Selecting the paragraph you mean sidesteps this: the query becomes the idea, not
the note that happens to contain it. Same reason `--search` exists, with the
phrase already written down.

### What this does *not* fix

`--duplicates` has no query, so none of this touches it. There the exposure is
sharper and should be tracked separately: date-shaped titles defeat the title
signal outright — `2026-09-04` vs `2026-09-05` scores **0.900** against a
`TITLE_MIN` of 0.85, and so does `2026-09-04` vs `2025-09-04` — leaving the 0.80
cosine bar as the only gate, which stub days already approach at 0.787. The
cheap mitigation is `--exclude` on the daily subtree for `--duplicates` runs.
See `bin/CLAUDE.md`.

## What already exists

Most of this is plumbing that is already in place.

- `ariadne_search.M.search(phrase)` (`search.lua:79`) takes arbitrary text and
  runs the whole async → JSON → picker path. A selection is just another phrase.
- `commands.lua:150` (`extract_note`) already reads a visual selection, with the
  `end_col` clamp that `V` and `$` selections need.
- `ariadne_embed_cache.best_chunk_match(query_chunks, doc_vector)` already scores
  a multi-chunk query against a note. Shipped in PLAN-0008.

The naive version — grab the selection, hand it to `M.search` — is ~20 lines of
Lua and no Python. The four questions below are what separate it from something
worth keeping.

## Open questions

### 1. The source note will be its own top hit

The selected text *is* text in a vault note, so that note scores near 1.0 and
takes the first row every time. Filtering it out in Lua afterwards makes
`cluster_total` and "N of M" lie, so it has to happen where the ranking does.

**Proposal:** `--search PHRASE --from NOTE VAULT`. `--from` names where the text
came from, which is exactly what licenses both behaviours — exclude that note,
and give the query a cluster (see 4). Note `split_positional()` currently treats
`--search` as vault-only, and `check_args()` refuses `--all`/`--no-bridge`
alongside it; both need revisiting.

*Alternative considered:* a separate `--similar-to-text` mode. Rejected on this
repo's own precedent — modes are flags on `ariadne-similar`, not new tools.

### 2. Is the query prefix right for a passage? — **needs measuring**

PLAN-0008 shipped `task: search result | query: X` for `--search` at +1.5% MRR,
**measured on title-shaped queries** — short, name-like. A selected paragraph is
document-shaped, and embeddinggemma prefixes documents differently, so the
result may not carry over and may invert.

**Measurement, on public corpora only** (`scratchpad/corpora`, per
`bin/CLAUDE.md`): on `younggulsong/my-wiki`, take a random 300–800 character
passage from note A as the query, and score against every note's stored vector.
Ground truth is A's own wikilinks — which is the real job, "I selected this
paragraph, show me related notes", rather than "find the note it came from".
Compare raw passage vs the query prefix vs the document prefix. Reuse
`qprefix_public.py`'s harness shape. ~5 minutes.

If the answer differs from the title case, `--from` is the natural signal for
choosing the prefix, since it distinguishes a typed phrase from lifted text.

### 3. A long selection is silently truncated

`--search` embeds the phrase as one vector, so a selected section loses its tail
past the model's context — the defect PLAN-0008 just removed for notes.

**Proposal:** window the selection and score with `best_chunk_match`, already
the shipped path for a multi-chunk target. Two snags: `note_chunks()` prefixes
every chunk with the note *name* and a selection has none; and `MAX_CHUNKS`
bounds a note, so a pasted selection needs its own bound or query cost is
unbounded.

### 4. Which ranking? — **confirm with the user before building**

`--search` groups by cluster *because* a typed phrase has no cluster of its own;
`--similar` ranks crossing-vs-within because a target note does. A selection sits
between: the text has none, the note it came from does.

**Proposal:** with `--from`, rank crossing-vs-within like `--similar`; without
it, group by cluster as today. This is a guess — PLAN-0007 settled the original
grouping question by asking first, and so should this.

## Lua side

- `:AriadneSearchSelection`, `range = true`, plus a visual-mode keymap.
  `<leader>oq` is `:AriadneSearch`; free letters in the `<leader>o` namespace
  are few — `oQ` is untaken.
- **Extract the selection reader into `utils.lua`, do not copy it.**
  `commands.lua:150` already has it including the `end_col` clamp, and this repo
  has twice paid down exactly this kind of duplication (`7be332d`, `d62b628`).
  A shared `utils.visual_selection()` is testable in `utils_spec.lua`, where the
  copy in `commands.lua` currently is not.

## Tests

- `utils_spec.lua`: `visual_selection()` over charwise, linewise, `$`-terminated
  and single-line selections — the clamp is the part that breaks.
- `ariadne_search_test.py`: `--from` excludes that note and nothing else; the
  cluster counts reflect the exclusion rather than being adjusted afterwards;
  a selection longer than one window is scored on its best chunk.
- Whatever question 2 settles, pin the chosen prefix the way
  `test_run_search_embeds_the_prefixed_phrase_not_the_raw_one` pins the current
  one.

```sh
cd bin && for f in *_test.py; do printf "%-34s " "$f"; python3 "$f" 2>&1 | tail -1; done
```

## Next action

Answer question 4 with the user — it decides the CLI shape, so it blocks the
rest. Then run the question 2 measurement, which is ~5 minutes and needs no
re-index. Only then write code.
