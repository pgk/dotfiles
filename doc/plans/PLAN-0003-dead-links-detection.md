# Dead link detection with fuzzy match suggestions

## Context

Building on [[PLAN-0001-notes-graph-health]] (orphan/sparse note detection via
`bin/notes-graph` + `:ObsidianGraphHealth`), the user wants a parallel feature: list
**dead links** (`[[wikilinks]]` that don't resolve to any note) across the vault,
each with **possible matches** — fuzzy-matched candidate note names, for the typo/
rename case ("did you mean `[[project-plan]]` instead of `[[projct-plan]]`?").

`bin/notes-graph` already resolves every link and collects `broken_links` per file
as a side effect of building its neighbor graph — but it only *surfaces* those
lists for notes that are already orphan/sparse (`classify()` only calls
`note_entry()` for degree `< min_links`). A well-connected note with one broken
link among its ten good ones is currently invisible to `:ObsidianGraphHealth`.

Decisions made with the user this session:
- **New standalone script**, not a flag on `notes-graph` — but the vault-walking /
  name-index / link-parsing logic the two scripts share gets **extracted into a
  common module**, not duplicated. This departs from PLAN-0001's "bin/ holds small
  single-purpose scripts, no shared modules" framing now that there's real overlap.
- **No third-party libraries.** Fuzzy matching uses stdlib `difflib.get_close_matches`
  — no new dependency, consistent with `notes-graph`'s existing stdlib-only build.
- **Picker action**: selecting a dead-link entry opens the **referring note** (the
  one containing the broken link), matching `:ObsidianGraphHealth`'s existing
  "select → edit that file" pattern. It does *not* jump to the suggested match —
  the suggestion is a hint shown as text, not a target, since a wrong guess would
  silently take you to the wrong note.
- Per [[feedback_notes_vault_privacy]]: built and tested against **synthetic**
  vaults only, `~/notes` is never read during development.

## Refactor: `bin/notes_common.py` (new shared module)

A real `.py` file (unlike the extensionless `notes-graph`/`notes-deadlinks`), so
both scripts and their tests can `import notes_common` directly after adding
`bin/` to `sys.path` — no `importlib.machinery.SourceFileLoader` needed for this
part. Not executable, no shebang — a library, like `bin/parse_enclosure.xsl` is a
non-executable support file already living in `bin/`.

Moved from `bin/notes-graph` verbatim (these four are used by both scripts):
- `iter_markdown_files(vault, excludes)`
- `build_name_index(files)`
- `extract_links(text)`
- `resolve_link(link_text, name_index)`

`notes-graph`'s `build_graph()` (neighbor-set + broken_links construction) stays
private — `notes-deadlinks` doesn't need a neighbor graph, only per-file
unresolved links. Both scripts add
`sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before
`import notes_common`.

## New script: `bin/notes-deadlinks`

Python 3, executable, no extension — matches `notes-graph`. Stdlib only
(`argparse`, `difflib`, `json`, `os`, `sys`, plus `notes_common`).

### Algorithm

1. `collect_dead_links(files, name_index)` — for each file: read it, run
   `notes_common.extract_links(text)`, resolve each via
   `notes_common.resolve_link`; targets that resolve to `None` are dead. Dedupe
   per file via `sorted(set(...))` (raw string, not case-folded — matches
   `notes-graph`'s existing per-note dedup behavior, so `[[Foo]]` and `[[foo]]`
   both broken still list as two entries, consistent with current precedent).
   Returns `{path: [dead_link_text, ...]}`, only for files with ≥1 dead link.
2. `suggest_candidates(link_text, name_index, limit=3, cutoff=0.5)` —
   `difflib.get_close_matches(link_text.lower(), name_index.keys(), n=limit,
   cutoff=cutoff)`, then map each matched (lowercased) key back to its on-disk
   display name via `os.path.splitext(os.path.basename(name_index[key]))[0]`
   (preserves original casing, since `name_index` keys are lowercased for
   lookup but values are real paths).
3. `build_report(dead_links_by_file, name_index)` — for each `(path, links)` in
   `dead_links_by_file` sorted by note name: build
   `{"name", "path", "dead_links": [{"link", "candidates"}, ...]}`, `dead_links`
   sorted by link text, `candidates` via `suggest_candidates` (empty list if none
   clear the cutoff — the entry still appears, as "no matches", matching
   `notes-graph`'s exhaustive orphan/sparse listing rather than hiding low-signal
   rows).
4. `format_text(report, total, vault)` / `format_json(report, total, vault)` —
   text mirrors `notes-graph`'s grouped style:
   ```
   Scanned 42 notes in /path/to/vault (3 dead links across 2 notes)

   note-a  (2 dead links)
     [[old-name]]  possible: new-name, renamed-note
     [[totally-made-up]]  no matches
   ```
   JSON: `{"vault", "total_notes", "notes_with_dead_links": [...]}` (empty-list
   case included for a clean "nothing found" JSON, same shape either way).
5. `parse_args(argv)` — `vault` positional (default `~/notes`), `--json`,
   `--exclude` (repeatable glob, reusing `iter_markdown_files`'s existing
   support — same use case as `notes-graph --exclude`, e.g. skipping a
   templates folder). No `--min-links`-equivalent: dead links have no threshold.
6. `main()` — wires the above, exit code always `0` (informational tool, matches
   `notes-graph`).

## Test changes

### `bin/notes_common_test.py` (new)
The shared-function tests currently in `notes-graph_test.py` move here:
case-insensitive resolution, `[[Alias|Display]]` resolving by target not
display text, `#heading` fragment stripping, `--exclude` glob filtering,
duplicate-stem warning behavior. Plain `import notes_common` — no
`SourceFileLoader` needed since it's a normal module.

### `bin/notes-graph_test.py` (updated)
Keeps only what's specific to `notes-graph`: `build_graph` neighbor/degree
construction, `classify` (orphan vs. sparse, `--min-links` threshold),
`format_text`/`format_json` shape, and the end-to-end subprocess test. Still
loaded via `SourceFileLoader` (extensionless), but now also has `notes_common`
importable via the same `sys.path.insert` the script itself does.

### `bin/notes-deadlinks_test.py` (new)
Same structure as `notes-graph_test.py`: synthetic vaults via
`tempfile.TemporaryDirectory`, loaded via `SourceFileLoader`. Coverage:
- A note with one broken link → appears with correct `candidates`.
- A note with all links resolved → absent from the report entirely.
- Multiple dead links in one note → grouped under that one entry, sorted.
- A near-miss typo (`[[projct-plan]]` vs. existing `project-plan.md`) surfaces
  as a top candidate.
- A dead link with nothing close in the vault → `candidates: []`, entry still
  present ("no matches").
- `--exclude` removes a matching file from the scan (so its dead links vanish).
- `--json` output shape and counts.
- One subprocess end-to-end test (`sys.executable`, script path, temp vault,
  `--json`).

Run with `python3 bin/notes_common_test.py`, `python3 bin/notes-graph_test.py`,
`python3 bin/notes-deadlinks_test.py` (all stdlib `unittest`, no install step).

## Neovim integration

New module `base/nvim/nvim/lua/plugins/obsidian/deadlinks.lua`, mirroring
`graph.lua`'s structure — same missing-binary message style, empty-result
short-circuit, and line→path lookup table for picker selections:
- `run_notes_deadlinks()`: checks `notes-deadlinks` is on PATH, runs
  `vim.system({ "notes-deadlinks", utils.vault_path, "--json" }, { text = true
  }):wait()`, decodes with `vim.json.decode`, validates the
  `notes_with_dead_links` key is a table.
- `M.check_dead_links()`: flattens `notes_with_dead_links[].dead_links[]` into
  one picker row per `(note, dead link)` pair, e.g.
  `note-a  [[old-name]]  possible: new-name, renamed-note` (or `no matches`
  when `candidates` is empty). Empty list → `vim.notify` "No dead links found"
  (INFO), no picker. Otherwise a line→path lookup table maps the selection to
  the **referring note's** path; opens `fzf-lua` `fzf_exec`, default action
  `vim.cmd.edit(path)`.
- `M.setup()` registers `:ObsidianDeadLinks`.

Wire into `init.lua`:
- `require("plugins.obsidian.deadlinks").setup()` alongside the other
  `.setup()` calls; update the header module list (lines 2-8).
- `vim.keymap.set("n", "<leader>oD", "<cmd>ObsidianDeadLinks<cr>", { desc =
  "Obsidian dead links" })` — capital `D`, next to `og`/`oR`; mirrors how `oR`
  (capital, Rename) sits alongside `or` (lowercase, random). Lowercase `od` is
  already daily notes.

Update `base/nvim/nvim/obsidian-workflow.md`: add `:ObsidianDeadLinks` to the
Commands table, `<leader>oD` to the Keybindings table, and a "Dead Links"
section under "Graph Health" describing the feature (mirrors that section's
structure: what it's backed by, what counts as a match, how selection behaves).

No `PATH` changes needed — `bin/` is already on `PATH`
(`base/bash/.profile`), so `notes-deadlinks` is callable both directly and via
`vim.system`.

## Verification

- `python3 bin/notes_common_test.py`, `python3 bin/notes-graph_test.py`,
  `python3 bin/notes-deadlinks_test.py` — all green.
- Manual CLI smoke test: hand-built synthetic temp vault with a clean link, a
  typo'd link with an obvious near-match, and a link to nothing resembling any
  note — run both plain and `--json`, eyeball output.
- `nvim --headless` (or interactively) pointed at a synthetic temp vault
  (never `~/notes`): run `:ObsidianDeadLinks`, confirm the picker lists the
  expected `(note, dead link)` rows with correct candidates, and that
  selecting one opens the *referring* note. Also test the zero-dead-links path
  and the missing-binary path.
