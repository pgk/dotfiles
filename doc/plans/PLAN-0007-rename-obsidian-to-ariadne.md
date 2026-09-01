# PLAN-0007 — Rename the `obsidian/` plugin to `ariadne/`

## Why

The Neovim Zettelkasten layer is its own thing, not a fork of `obsidian.nvim`;
it only sits on top of it. Naming it `obsidian/` made the boundary between
"our code" and "upstream's code" invisible — the directory, the commands and
the upstream plugin all answered to the same word. `ariadne` names the thread
through the labyrinth, and inherits the name of the retired `~/dev/ariadne`
project whose salvageable findings land here too.

## Scope

### Renamed

- `base/nvim/nvim/lua/plugins/obsidian/` → `.../ariadne/`, and the 31
  `require("plugins.obsidian.*")` paths that reach into it.
- The 15 **custom** user commands, `:Obsidian*` → `:Ariadne*`.
- `base/nvim/nvim/obsidian-workflow.md` → `base/nvim/nvim/ariadne.md`,
  plus `HELP_DOC` in `commands.lua`.
- `utils.run_notes_tool` → `utils.run_ariadne_tool`; it names the tools below.
- `bin/notes-*` → `bin/ariadne-*` (4 executables), `bin/notes_*.py` →
  `bin/ariadne_*.py` (12 modules + testkit), and every `_test.py` counterpart.

### Deliberately not renamed

- `require("obsidian")`, the `obsidian-nvim/obsidian.nvim` lazy spec, and
  `lazy-lock.json` — that is the upstream plugin.
- `:Obsidian search` / `new` / `backlinks` / `links` — upstream's own commands,
  bound at `<leader>os/on/ob/of`.
- The `<leader>o` keymap prefix. `<leader>a` is free, but 18 keys of muscle
  memory is not worth the churn; the prefix can move later on its own.
- The `~/notes` vault path and the `notes` workspace name in `opts`.

## Salvage from `~/dev/ariadne`

`SALVAGE.md` is mostly about an LLM extraction pipeline that this project
deliberately does not have. Two findings port; the rest is already covered here
or does not apply.

Already covered: embedding the title with the body (`note_text()` is
`name\n\nbody`); skipping dot-prefixed path components and symlinks when
walking a vault (`iter_markdown_files`). Not applicable: pinning
`sentence-transformers` to CPU and the numpy `search_flat()` — embeddings here
go over HTTP to a local server and the cache is stdlib `math.sumprod`.

### 1. Strip wikilinks before embedding

`[[Working Memory]]` should embed as the words a reader sees, not as
punctuation. `[[title|alias]]` embeds as the alias, `[[title#heading]]` as the
title. Changes every note's content hash once, so it forces one re-index.

### 2. Duplicate detection needs two signals

Measured on a 37-note corpus in the old repo: the one genuine duplicate scored
0.842 embedding / 1.000 title, while every other pair above 0.80 embedding
scored ≤ 0.430 on title. So **0.80 cosine to be a candidate, 0.85 title
similarity (`difflib.SequenceMatcher`) to call it a duplicate**, and the band
between is a question for a human rather than an answer. Embedding similarity
alone cannot separate "the same note twice" from "a neighbouring idea".

Shipped as `bin/ariadne_duplicates.py` (the two signals, plus the mode's own
argparse block and runner), `ariadne-similar --duplicates` with `--dup-min` /
`--dup-title-min` so the borrowed thresholds can be re-tuned here, and
`duplicates.lua` → `:AriadneDuplicates` / `<leader>ou`. The picker opens either
side of a pair, or both in a split. The scan is every-pair with no index — tens
of seconds on a few thousand notes — so it is its own mode and its own async
command, never something a query pays for.

Extracting the mode into its own module kept `ariadne-similar` under the
400-line limit; it ends at 356.

### Recorded, not ported

- `ariadne-similar`'s ranking is uncalibrated in the same way the old repo's
  `pairs.py` 0.65 bar was: tuned before titles joined the embedding input.
- The old project retired "a vector index as the primary retrieval surface" —
  embeddings are for "find the note I half-remember", not for assembling
  context. `ariadne-similar` is already doing the first job; keep it there.
