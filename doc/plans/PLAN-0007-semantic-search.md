# Semantic search by phrase, grouped by cluster

## Context

Requested this session: search the vault by a free-text phrase or word,
ranked by meaning rather than shared vocabulary — the same embedding index
`ariadne-similar` already builds, but queried with arbitrary text instead of
an existing note. Confirmed with the user: results should be **grouped by
cluster** rather than a flat top-N, so one tight cluster's near-duplicate
notes cannot bury a good match sitting in a different part of the vault.

**The codebase moved since the last plan landed** — renamed `notes-*` →
`ariadne-*`/`Ariadne*` throughout, plus `--duplicates` (near-duplicate
detection) and folgezettel branching landed in between. This plan targets the
current `ariadne-*` layout, not the `notes-*` one from PLAN-0004/0006.

`ariadne_duplicates.py` is the template to follow: a self-contained module
bolted onto `ariadne-similar` via three seams (`add_arguments`,
`check_arguments`, `run`), with its own report functions in
`ariadne_similar_report.py` and its own test file. This adds a fourth mode
the same way.

## Design

### CLI: `ariadne-similar --search "phrase" VAULT`

A third `vault_only` mode alongside `--index`/`--duplicates` in
`split_positional()` — takes just VAULT, phrase comes from `--search` itself
(`type=str`, default `None`, mode active when not `None`). Not named
`--query`: that word already means "a target-note comparison" throughout this
codebase's own comments and messages, and reusing it for free text would be
genuinely ambiguous, not just a style nit.

Mutual exclusion in `check_args()` generalizes from the current pairwise
`--index`/`--duplicates` check to an n-way one (there are three modes now,
not two):

```python
modes = [("--index", args.index), ("--duplicates", args.duplicates), ("--search", args.search is not None)]
active = [name for name, on in modes if on]
if len(active) > 1:
    raise ValueError(f"{' and '.join(active)} are separate modes; run them one at a time")
```

`--all`/`--no-bridge` extend their existing "applies to a query, not
--duplicates" refusal to cover `--search` too — neither means anything
without a target note.

### New file: `bin/ariadne_search.py`

Mirrors `ariadne_duplicates.py`'s shape exactly: pure ranking function, plus
`add_arguments`/`check_arguments`/`run`/`report_unavailable`. Deliberately
knows nothing about clustering, embedding, or the cache — same reason
`ariadne_duplicates.py` only takes `(notes, cached)`, testable with hand-built
inputs, no mocking the pipeline around it.

```python
def rank_by_cluster(query_vec, notes, cached, clusters, *, per_cluster, limit):
    # cosine each embedded note against query_vec, grouped by clusters[path];
    # within a cluster: top `per_cluster` by score, ties by name
    # clusters ordered by their own best hit; only the top `limit` clusters kept
    -> list[{"cluster": int|None, "cluster_total": int, "hits": [...]}]

def add_arguments(parser):
    # --search PHRASE (mode flag + the phrase itself)
    # --per-cluster N, default 3 — hits shown per cluster

def check_arguments(args):
    # --per-cluster >= 1; --search phrase (if the mode is active) is non-blank

def run(args, vault, notes, cached, clusters, shape, query_vec) -> int
def report_unavailable(args, vault, total, error)
```

`--limit` (existing flag, default 10) is reused for "clusters shown" — its
meaning already varies by mode (bridge-mode: per-group; `--duplicates`: caps
only the "possible" band), so this extends an established pattern rather than
starting a new one.

**No score floor, no preview field** — matching precedent: the existing
target-mode has no floor either, and `--duplicates`' own pairs carry no
preview (score/names/paths only). Both are easy to add later without a
redesign, not designed in now against unmeasured numbers.

### Query embedding

`ariadne-similar`'s `main()` computes `clusters`/`shape` and the query vector
itself, then hands them to `ariadne_search.run()` — the same place it already
computes `clusters, shape = cluster_notes(notes, name_index)` for target-mode:

```python
if args.search is not None:
    cached = load_or_refresh(args, vault, notes, embedder)
    clusters, shape = cluster_notes(notes, name_index)
    print(f"ariadne-similar: sending your search phrase to "
          f"{ariadne_embed_client.safe_url(args.endpoint)} ({_printable(args.model)})", file=sys.stderr)
    query_vec = embedder([args.search])[0]
    return ariadne_search.run(args, vault, notes, cached, clusters, shape, query_vec)
```

The explicit announce line matters: `embed_batch()` doesn't print one itself
(callers do), and every other embedding call in this tool announces before
sending — silently skipping it for the query phrase would be a real gap in
the "never embed without saying what is being sent where" rule, even though a
typed phrase is less sensitive than note content. The query vector is never
written to `~/.cache/ariadne-similar/` — one-off, computed fresh, read-only
against the existing index, same boundary `--duplicates` already respects by
never writing there either.

`EmbedUnavailable` from the query embed call is caught by the same outer
`except` block that already wraps `--index`/`--duplicates`/target-query, so it
degrades the same way (clean message, valid JSON, exit 0) with no special
casing needed.

### `ariadne_similar_report.py`

New `format_search_text`/`format_search_json`, alongside the existing
`format_text`/`format_json` (target-mode) and `format_duplicates_text`/`_json`
(duplicates-mode) — same file, same one-pair-of-functions-per-mode pattern.
Text report groups by cluster with a header per group
(`cluster 3 (3 of 11)`), mirroring `format_duplicates_text`'s
"N of total" convention for a truncated band.

### Neovim: new `search.lua`, not folded into `similar.lua`

Own file, matching how `--duplicates` got its own `duplicates.lua` despite
sharing the `ariadne-similar` backend. `:AriadneSearch [phrase]` — with an
argument, searches immediately; without one, prompts (`vim.fn.input`), same
fallback pattern `commands.rename` already uses for its note-name argument.
Async via `vim.system`, matching `similar.lua`/`duplicates.lua`. Picker rows
carry an inline `[cluster N]` tag (matching `graph.lua`'s `[SPLIT]`/`[NO HUB]`
prefix convention) rather than synthetic non-selectable header rows, since
fzf-lua's model is a flat list.

`<leader>oq` on `AriadneSearch` — `<leader>os`/`<leader>oS` are already
`Obsidian search` (lexical) and `AriadneSimilar` (note-to-note); a third,
easily-confused "search" needs a clearly different key, not an adjacent one.

`cli.lua`'s `decode`/`header_for`/`relative` are reused as-is — this is
exactly the shared surface it exists for.

## Tests

`bin/ariadne_search_test.py`, one file covering ranking, report formatting,
CLI argument validation, and CLI integration — mirroring
`ariadne_duplicates_test.py`'s all-in-one-file shape exactly (`FindDuplicatesTests`
+ `ReportTests` + `CliTests` + `ArgumentTests` there maps to
`RankByClusterTests` + `ReportTests` + `CliTests` + `ArgumentTests` here).

`notes_and_cache(files)` — currently a private helper duplicated for
`ariadne_duplicates_test.py`'s own use — moves into `ariadne_similar_testkit.py`
as a shared helper, since this file needs the identical thing: a vault, fully
embedded, as `(notes, cached)`. Small, justified refactor while touching
adjacent code, not scope creep — same category as moving `strip_frontmatter`
in PLAN-0006.

Coverage:

- grouping: per-cluster cap keeps the top N by score, ties broken by name
- cluster cap (`--limit`): clusters ordered by their own best hit, weakest
  clusters dropped, never a cluster's *internal* ordering disturbed
- a note with no cached embedding is skipped, not crashed on
- report: empty result is one line; a truncated cluster says "N of total"
- CLI: `--search` mutually exclusive with `--index` and `--duplicates`
  (extend the n-way check); `--all`/`--no-bridge` refused under `--search`;
  blank/whitespace-only phrase refused; `--per-cluster < 1` refused
- `--json` payload shape: `groups: [{cluster, cluster_total, hits}]`

## Docs

`ariadne/CLAUDE.md` gets a short paragraph under "What `ariadne-similar`
embeds", parallel to the existing `--duplicates` paragraph there. `ariadne.md`
gets a "Semantic Search" section matching the existing "Similar Notes" one,
plus the keybindings/commands tables. `bin/CLAUDE.md` — check whether it lists
`ariadne-similar`'s modes explicitly; add `--search` if so.

## Next action

Build order: `ariadne_search.py` + its tests first (pure logic, no CLI/Lua
dependency), then wire into `ariadne-similar`, then `search.lua` +
`init.lua`. `/done` (code + security review) before calling it finished, same
as PLAN-0006.
