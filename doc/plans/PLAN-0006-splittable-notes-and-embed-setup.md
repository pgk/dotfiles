# Splittable-note detection, and an embed-model setup script

## Context

Discussed and researched this session, before any code: a category for notes
that have grown past one idea's worth of content and should become several
atomic notes.

**This idea was already explored and partly closed.**
`doc/plans/PLAN-0005-local-llm-notes-exploration.md` (deleted after landing,
commit "Remove PLAN-0005, its work is complete") ran a full local-LLM
exploration for this vault and closed "LLM note splitting into atomic notes":
*"requires knowing where one idea ends — not surface-determinable."* Same
reasoning killed LLM-based tag backfill and grammar fixing. See
`[[project-notes-vault-llm-decisions]]` (auto-memory) for the full closed-idea
table — read it before proposing any LLM-based feature for this vault again.

Put to the user directly: keep the idea, drop the LLM. **Heuristic only, and it
must not split anything itself.** What follows never claims to know where an
idea ends — it surfaces structural facts (word count, the note's own headers,
outbound link count) and leaves the judgment and the editing to the reader, at
the note. That keeps it on the safe side of the surface-determinable line the
closed table drew, and it was never itself in that table — the table is about
an *LLM* doing the judging.

Two deliverables, unrelated in function, both raised this session:

1. `ariadne-graph --splittable`-equivalent: a third node-level health category,
   alongside the existing orphans/sparse.
2. `bin/ariadne-embed-setup`: prompted by hitting a second machine that runs
   Ollama but doesn't have `embeddinggemma` pulled yet — `ariadne-similar` has no
   way to say "get the model for me."

## 1. Splittable notes

### Heuristic

```
candidate = (header_count >= MIN_HEADERS or word_count >= MIN_WORDS)
            and out_degree < MAX_OUT_DEGREE
```

- **`MIN_HEADERS = 3`** (`##`/`###`, not the title `#`). Three or more named
  sections means the note has already delineated separate sub-topics, which is
  a better signal for "several ideas" than length alone — a long single-topic
  deep-dive isn't a split candidate just because it's long.
- **`MIN_WORDS = 1200`**, OR'd in as a fallback for headerless sprawl (a long
  note that never got structured). PLAN-0005 measured the real vault at ~177
  words/note; 1200 is ~7x that — a real outlier, not a normal note.
- **`MAX_OUT_DEGREE = 8`**, as a negative filter: a note linking out to many
  others is plausibly a map-of-content organizing them, not a candidate to be
  broken up. `ariadne-graph`'s existing "sparse" threshold is `min_links = 3`
  (an undirected, symmetrised degree); 8 sits well above that on **out-degree
  specifically** — see below for why the distinction matters. All three are
  new `--min-headers` / `--min-words` / `--max-out-degree` flags, not hardcoded,
  matching `--min-links`'s existing pattern.

**Output includes the note's own header titles verbatim**, as candidate split
points — e.g. `sections: Background / Approach A / Approach B / Open
questions`. That's a fact about the note, not a judgment about it, so it's free
to show.

### Why this needs its own scan, not `ariadne_cluster.build_graph`

`ariadne_cluster.adjacency_from_links` deliberately builds an **undirected**
graph (`neighbors[path].add(target); neighbors[target].add(path)` both run),
which is why every existing `degree` field in this codebase (orphans, sparse,
`ariadne_neglected.py`) can't distinguish "links out to 20 others" (an MOC) from
"is linked from 20 others" (a popular concept page). Splittable notes need
outbound count specifically.

Rather than change `build_graph`'s return shape (shared, tested, single
current caller but still shared infrastructure) or add a directed-degree
concept to `ariadne_cluster.py`, `ariadne_splittable.py` does its own independent
read pass — text, frontmatter-stripped word count, headers, and its own
link-resolution loop for out-degree — the same way `ariadne-similar` already
scans independently rather than reusing `ariadne-graph`'s pass. Real seam, not
an arbitrary one: this module's concern is note *text*, `ariadne_cluster.py`'s
is link *topology*.

Frontmatter stripping currently lives as a private function in `bin/ariadne-similar`.
Move it to `ariadne_common.strip_frontmatter` — shared by both, and worth doing
regardless (same category as `ariadne-deadlinks` still carrying its own private
copy of `printable()`, noted as tech debt in PLAN-0004).

### New file: `bin/ariadne_splittable.py`

Mirrors `ariadne_neglected.py`'s shape:

```python
def note_stats(path, raw, name_index, files_set) -> dict
    # words, headers (list of title strings), out_degree

def select(files, name_index, min_headers, min_words, max_out_degree, vault)
    -> (candidates, considered)
    # candidates sorted by -words, then name

def format_text(entries, considered, total, vault, min_headers, min_words, max_out_degree) -> str
def format_json(...) -> str
```

`out_degree` resolves each `[[link]]` via `ariadne_common.resolve_link` and
counts distinct targets in `files` — same resolution/self-exclusion logic
`adjacency_from_links` uses, just not symmetrised, and duplicated rather than
extracted for the reason above.

### Wiring into `bin/ariadne-graph`

New flags `--min-headers` (default 3), `--min-words` (default 1200),
`--max-out-degree` (default 8). Splittable results become a third category in
the **default** health report (alongside `orphans`, `sparse`,
`hubless_clusters`) — not a mode switch like `--since`/`--neglected`, since
those exist because a temporal view would otherwise bury a small result under
volume; splittable is structural like orphans/sparse and belongs beside them.
`format_text`/`format_json` gain a `splittable` section/key.

`ariadne_splittable.select()` takes `files` and `name_index`, which
`ariadne-graph`'s `main()` already has before it calls `build_graph` — no
ordering dependency either way.

**Check when implementing:** `ariadne_cluster_test.py` may assert `build_graph`'s
exact return shape — irrelevant here since it's untouched, but worth
confirming nothing else assumes graph-building is the only per-note text read
in a `ariadne-graph` invocation.

### Neovim: extend `:AriadneGraphHealth`, no new command

`graph.lua` already renders orphans/sparse/hubless from one JSON payload; add
a `[SPLIT]`-prefixed section the same way hubless rows are marked
`[NO HUB]`. Selecting a row **opens the note** — same as every other row in
this picker — so the user reads it and decides whether and how to split it
themselves. Nothing in this feature ever writes to a note.

### Tests

`ariadne_splittable_test.py`, same harness as `ariadne_neglected_test.py`
(`tempfile.TemporaryDirectory()`, never `~/notes`):

- word/header counting, frontmatter stripped first
- out-degree excludes self-links, broken links, links outside the scanned set
- gate: headers-only pass, words-only pass, both-fail, out-degree veto
- header titles preserved verbatim and in document order for the "sections:" line
- text/JSON formatting

`dev-vault/` needs at least one new fixture that legitimately passes the gate
(long, multi-section, few outbound links) and one MOC-shaped fixture (many
outbound links, would otherwise pass on headers/words alone) to prove the veto
fires — update its `CLAUDE.md` section when added, per its existing convention.

## 2. `bin/ariadne-embed-setup`

Ensures the Ollama model `ariadne-similar` needs is present, pulling it if not.
Scope is deliberately Ollama-only — `/api/tags` and `/api/pull` aren't part of
the OpenAI-compatible surface `ariadne_embed_client.py` targets, so this can't
be made server-agnostic the way the embeddings client is. Says so in
`--help`; LM Studio / `llama-server` users pull models through their own
tooling.

Shells out to the `ollama` binary rather than reimplementing its pull-progress
streaming protocol — `ollama list` to check, `ollama pull <model>` to fetch,
inheriting stdio so the pull's own progress output shows normally.

```python
#!/usr/bin/env python3
"""Ensure the Ollama model ariadne-similar needs is pulled on this machine."""

def model_present(model) -> bool
    # `ollama list`, match name or name:tag

def main(argv=None) -> int
    # --model (default $NOTES_EMBED_MODEL or ariadne_embed_client.DEFAULT_MODEL)
    # --check (report only, don't pull)
    # no `ollama` on PATH -> exit 1, clear message
    # present -> print + exit 0
    # missing, --check -> print + exit 1
    # missing, pull -> `ollama pull <model>`, exit its returncode
```

No vault, no note content, no network code of its own — every network access
happens inside the `ollama` binary, not this script. `ariadne-embed-setup_test.py`
puts a fake `ollama` shell script on a temp `PATH`, covering: already present,
missing-and-pulled, missing-and-`--check`, pull fails, `ollama` absent.

## Built, reviewed, and closed out

Both tools shipped in build order. `code-reviewer` and `security-reviewer` ran
in parallel per `/done`; both came back clear after fixes. What changed from
the plan above:

- `select()` returns just the candidate list, not `(candidates, considered)`
  — there is no `--limit` here to make "considered vs. shown" meaningful, so
  the extra return value from the `ariadne_neglected.py`-style draft was dropped.
- `format_text`/`format_json` for splittable rows never became a standalone
  pair; `ariadne_splittable.format_lines()` returns picker/report lines that
  `ariadne-graph`'s existing formatters splice in, matching `format_hubless`.
- **Two real bugs found by review, both in `HEADER_RE`**, caught independently
  by both reviewers converging on the same code: `\s+` crossed a blank header
  line into the next paragraph and counted it as a title; headers inside
  fenced code blocks counted toward the gate. Fixed with `[ \t]+` and a
  fence-strip pass before counting.
- **The out-degree veto boundary (`<` vs `<=`) had no test** — mutation-tested
  by the reviewer, who flipped it and found the whole suite (dev-vault
  fixture included) still green. Added a unit boundary test and a dev-vault
  fixture-level test, both confirmed to catch the mutation.
- `ariadne-embed-setup`: a differently-tagged model (`embeddinggemma:300m`)
  falsely read as "present" when the unqualified default implies `:latest`;
  `--model=--insecure` reached `ollama pull` unvalidated; terminal output
  wasn't run through `ariadne_common.printable()`. All three fixed and tested.
- Added `:AriadneHelp` (`<leader>oh`) in the same session, unplanned —
  opens this repo's `ariadne.md` from a path computed off
  `commands.lua`'s own location. Prompted by "should there be a help command,"
  asked after the two tools above were already done.

## Next action

Nothing queued. `git status` still shows everything uncommitted as of this
write-up — commit history for this work is whatever landed after it.
