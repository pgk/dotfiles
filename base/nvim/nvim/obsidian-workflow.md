# Obsidian Workflow in Neovim

This document describes the custom Obsidian integration for Neovim, built on top of [obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim).

## Vault Location

`~/notes`

## Keybindings

### Global (available anywhere after startup)

| Key | Command | Description |
|-----|---------|-------------|
| `<leader>od` | `:ObsidianDaily` | Open today's daily note (with template) |
| `<leader>or` | `:ObsidianRandom` | Open a random note |
| `<leader>ol` | `:ObsidianLinksPanel` | Toggle links panel sidebar |
| `<leader>os` | `:Obsidian search` | Search vault (fulltext) |
| `<leader>on` | `:Obsidian new` | Create a new note |
| `<leader>oi` | `:ObsidianInsertLink` | Search vault and insert link at cursor |
| `<leader>ob` | `:Obsidian backlinks` | Backlinks in picker |
| `<leader>of` | `:Obsidian links` | Forward links in picker |
| `<leader>ot` | `:ObsidianTransclusionToggle` | Toggle transclusion rendering |
| `<leader>oR` | `:ObsidianRename` | Rename note and update all links |
| `<leader>og` | `:ObsidianGraphHealth` | Find orphans, sparse notes, splittable notes, and clusters with no hub |
| `<leader>oa` | `:ObsidianActive` | Notes touched recently, grouped by link community |
| `<leader>oh` | `:ObsidianHelp` | Open this doc |
| `<leader>oD` | `:ObsidianDeadLinks` | Find dead links and possible matches |
| `<leader>oS` | `:ObsidianSimilar` | Find semantically similar but unlinked notes |

### In Markdown Files

| Key | Description |
|-----|-------------|
| `gf` | Smart follow link (works on `[[` or `]]` too) |
| `<leader>ch` | Toggle checkbox |
| `[[` | Triggers completion for note links |

### In Links Panel

| Key | Description |
|-----|-------------|
| `<CR>` / `o` / `gf` | Open link under cursor |
| `q` | Close panel |
| `<C-w>h` | Return to main window |

## Commands

| Command | Description |
|---------|-------------|
| `:ObsidianRandom` | Open a random note from vault |
| `:ObsidianLinksPanel` | Toggle the links panel sidebar |
| `:Obsidian search` | Fulltext search across vault |
| `:Obsidian new` | Create a new note |
| `:ObsidianInsertLink` | Search and insert a `[[link]]` at cursor |
| `:ObsidianDailyReview` | Add 5 random notes to today's daily note |
| `:Obsidian backlinks` | Show backlinks in picker (built-in) |
| `:Obsidian links` | Show forward links in picker (built-in) |
| `:ObsidianTransclusionToggle` | Toggle inline transclusion rendering |
| `:ObsidianRename [name]` | Rename current note and update all links |
| `:ObsidianDaily [offset]` | Open daily note with template (offset: -1 = yesterday, 1 = tomorrow) |
| `:ObsidianGraphHealth` | Find orphans, sparse notes, splittable notes, and clusters with no hub (picker) |
| `:ObsidianActive [7d]` | Notes touched in a recent window, grouped by cluster (picker) |
| `:ObsidianHelp` | Open this doc |
| `:ObsidianDeadLinks` | Find dead links and possible matches (picker) |
| `:ObsidianSimilar` | Find semantically similar but unlinked notes (picker) |
| `:ObsidianSimilarIndex[!]` | Refresh the embedding index in the background (`!` rebuilds from scratch) |

## Links Panel

The links panel (`<leader>ol`) shows a sidebar with:

- **Forward Links**: Notes linked from the current note, with preview text
- **Backlinks**: Notes that link to the current note, with context

The panel updates automatically when you switch buffers. Navigate to a link and press `<CR>` to open it.

## Daily Notes Workflow

New daily notes are automatically created with a template:

```markdown
Daily note for 2026-09-01

Previous #daily-note was: [[2025-08-30]]


- [[random-note-1]]
- [[random-note-2]]
- [[random-note-3]]
- [[random-note-4]]
- [[random-note-5]]

## On this day

- [[2025-09-01]] (1 year ago)
- [[0020240901-7]] (2 years ago)

## Neglected

- [[harbour-metaphor]] - 12 links, untouched 14 months
- [[gardening-as-editing]] - 9 links, untouched 11 months
```

Three ways in, each answering a different question:

- **5 random notes** — pure serendipity, no criteria.
- **On this day** — notes dated today in an earlier year. The date comes from the
  filename (`YYYY-MM-DD`, `YYYY-MM-DD-title`, `YYYYMMDD-title`, or the
  `00YYYYMMDD-N` names the old `mknote` wrote) and otherwise from the file's
  mtime. Birthtime is deliberately not used — whether sync preserves it has never
  been measured. Absent on a day with no anniversaries.
- **Neglected** — well-connected notes you have not touched in 180 days, from
  `notes-graph --neglected`. Three are sampled from the 50 best connected rather
  than taken in rank order, so the same notes do not reappear every morning.
  Absent if `notes-graph` is not on `PATH` (you get a warning instead).

Workflow:
1. `<leader>od` - Open/create today's note
2. Review the random notes, add thoughts
3. Use `<leader>oi` to insert links to related notes

## Renaming Notes

Use `<leader>oR` or `:ObsidianRename` to rename the current note:
- Prompts for new name (pre-filled with current name)
- Renames the file
- Updates all `[[links]]` across the vault automatically

## Graph Health

Use `<leader>og` or `:ObsidianGraphHealth` to find structural problems in the
vault, at two levels:
- Backed by the `notes-graph` CLI tool (`bin/notes-graph` in dotfiles). It reads
  only the link graph and note text — no embedding server, no network, no LLM
- **Per note:** orphans have zero `[[links]]` in or out; sparse notes are below
  the connection threshold (default: 3, see `notes-graph --help`); `[SPLIT]`
  rows are notes that have grown past one idea's worth of content — at least 3
  `##`/`###` sections, or 1200+ words for headerless sprawl — and aren't
  themselves acting as a map of content (8+ outbound links vetoes the flag).
  It's a structural signal only: no claim about where one idea ends, just
  that the note is long/multi-section and not an index. The `notes-graph` CLI
  report (not the picker, which shows only the counts) lists the note's own
  section titles as candidate split points; nothing is ever split
  automatically. Tune with `--min-headers` / `--min-words` / `--max-out-degree`
- **Per cluster:** `[NO HUB]` rows are link communities that no note links to
  enough of to serve as a way in. That is an actionable "write a map of content
  here". A note that indexes its cluster reaches all of it; the threshold is half
  (`--hub-reach`). Small clusters are never reported, because you cannot help but
  reach most of a four-note group — the finding only becomes real at a size where
  no single note can index the group
- Hubless clusters are listed first, since a few of them would otherwise be
  buried under hundreds of sparse notes. Selecting one opens the note that comes
  closest to being its entry point — the one you would promote, or write beside
- The picker header states the graph it ran on: components, cluster count and
  modularity. Many tiny components, or a modularity near zero, means there are no
  real clusters and the `[NO HUB]` rows are noise
- Select any row to jump to that note

## A note on command names

Commands in the `:Obsidian <subcommand>` form belong to obsidian.nvim itself. The
`:ObsidianXxx` ones are this config's own — they are ordinary user commands and are
not affected by the plugin's `legacy_commands` deprecation, which is set to `false`
here.

## Recent Activity

Use `<leader>oa` or `:ObsidianActive` to see what you have actually been working on.
Where graph health is an audit you run occasionally, this is a daily view:

- Backed by `notes-graph --since` (`notes-graph ~/notes --since 7d`). Takes a window
  like `7d`, `36h` or `2w`; `:ObsidianActive 2w` passes it through, default `7d`
- Notes touched in the window are **grouped by link community**, and the communities
  are ranked by how many of their notes you touched. That answers "what was I working
  on" better than a flat list of filenames does — `[c4 12/86]` means twelve of that
  cluster's eighty-six notes
- **`[ORPHANED]` rows are the point of the view**: notes you touched that still have
  no links at all. You wrote them and never connected them, and you still remember
  the context
- Clusters and degrees are always computed over the **whole vault**, never just the
  window — a note linked from fifty older notes is well-connected, not an orphan

This relies on file modification times, so it is only as good as they are. If
something rewrites mtimes across your vault (a sync client, a bulk reformat), the
window fills with notes you did not touch. Check with
`find ~/notes -name '*.md' -mtime -7 | wc -l` against your total.

## Dead Links

Use `<leader>oD` or `:ObsidianDeadLinks` to find `[[wikilinks]]` that don't resolve
to any note:
- Backed by the `notes-deadlinks` CLI tool (`bin/notes-deadlinks` in dotfiles)
- Each dead link is shown with up to 3 fuzzy-matched candidate note names (or "no
  matches"), for the typo/rename case
- Results open in an fzf-lua picker, one row per `(note, dead link)` pair; select
  one to jump to the **referring note** so you can fix the link — not to the
  suggested match, since a wrong guess would silently take you to the wrong note

## Similar Notes

Use `<leader>oS` or `:ObsidianSimilar` to find notes that are *about* the same
thing as the current one but aren't linked to it — the connection you meant to
make and forgot. Where `:ObsidianGraphHealth` finds notes with too few links and
`:ObsidianDeadLinks` finds links pointing nowhere, this finds the links that were
never made:

- Backed by the `notes-similar` CLI tool (`bin/notes-similar` in dotfiles), which
  compares notes by meaning rather than by shared words, so a match doesn't depend
  on the two notes using the same vocabulary
- Notes already linked in **either** direction are filtered out, so every row is a
  connection you don't have yet
- Rows that **bridge clusters** come first, marked `[cluster N]`. A similar note
  already sitting in the current note's own neighbourhood mostly restates a
  connection the graph has; one from a different cluster is a link the vault
  doesn't have any route to. Within-cluster hits still follow, under their own
  limit, so you can see both — the comparison is the point
- The picker header states the graph the clustering ran on: components, cluster
  count and modularity. Many tiny components, or a modularity near zero, means
  there are no real clusters and the `[cluster N]` marks are noise
- Results open in an fzf-lua picker. `<CR>` opens the note so you can read it
  first; `<C-y>` inserts `[[the-note]]` at your cursor instead

### Setup

Similarity needs a local embedding server. With [Ollama](https://ollama.com):

```sh
ollama pull embeddinggemma
notes-similar --index ~/notes    # or: export NOTES_VAULT="$HOME/notes"
```

`notes-embed-setup` automates that first line: pulls the model if it's
missing, or with `--check` just reports whether it is. Ollama-only (shells
out to `ollama list`/`ollama pull`); on LM Studio or `llama-server`, pull the
model through that tool's own UI or CLI instead.

`embeddinggemma` is multilingual, which matters for the non-English notes in the
vault. Any OpenAI-compatible server works — point `NOTES_EMBED_URL` at LM Studio
or `llama-server` instead, and set `NOTES_EMBED_MODEL` to its model name.

The first index embeds the whole vault and takes a few minutes; everything after
that is incremental, since only notes whose text changed get re-embedded. Vectors
are cached in `~/.cache/notes-similar/` (mode `0600`, no note text — just paths,
hashes, and vectors), never inside the vault.

`:ObsidianSimilar` re-embeds edited notes on the fly, but refuses to do a full
index from inside the picker — if a lot of notes are unindexed it says so and
asks you to run `:ObsidianSimilarIndex` (or the CLI) instead. The CLI call is
async, so neither command blocks the editor.

If the embedding model is ever swapped for one with a different vector size,
`:ObsidianSimilarIndex!` (or `notes-similar --index --rebuild <vault>`) discards
the cache and starts over.

Clustering itself needs no server and no index — it reads only the wikilink
graph. `notes-similar --no-bridge` turns the grouping off and ranks purely by
similarity.

### Where your notes go

To keep a subtree out of the index entirely, pass `--exclude` — `notes-similar
--index --exclude journal ~/notes`. It matches directory names as well as globs, is
case-insensitive, and warns if a pattern matched nothing, since a typo there would
silently upload the notes you meant to hold back.

`notes-similar` is the only tool in this workflow that sends note text off-process,
so it is deliberately noisy and restrictive about it:

- Before embedding anything it prints `sending N note(s) from <vault> to <endpoint>`,
  which the picker surfaces as a notification
- A non-loopback endpoint is **refused** unless you pass `--allow-remote-endpoint`,
  so a stray `NOTES_EMBED_URL` can't quietly ship the vault to a remote host
- Every invocation must name the vault — there is **no** `~/notes` default, because
  an option or a shell quoting slip swallowing the argument would otherwise point
  the tool at the real vault silently. For CLI convenience, set it once:

  ```sh
  export NOTES_VAULT="$HOME/notes"
  ```

  The Neovim commands always pass the vault explicitly, so they are unaffected.

**With no embedding server running, nothing breaks:** the command reports that
embeddings are unavailable and does nothing. The rest of the workflow is unaffected.

## Quick Capture Workflow

1. `<leader>on` - Create a new note
2. Write your content
3. Use `[[` to link to existing notes (completion available)
4. Or use `<leader>oi` to search and insert links

## Navigation Workflow

1. Open any note
2. `<leader>ol` - Open links panel to see connections
3. `<C-w>l` - Focus the panel
4. Navigate to a link, press `<CR>` to open
5. `gf` on any `[[link]]` in the main editor to follow

## Transclusion

Use `![[note-name]]` syntax to embed another note's content. Toggle rendering with `<leader>ot`.

When enabled, transclusions render as:
```
![[some-note]]
  ┌─ some-note
  │ First line of the note...
  │ Second line...
  │ ...
  └────────────────────────────────────────
```

- Content is read-only (virtual text)
- Shows entire file content
- Skips YAML frontmatter
- Wraps long lines to fit window
- Markdown highlighting (headers, lists, links, bold)
- Auto-updates as you edit

## Markdown Settings

- Soft word wrap enabled (visual only, no hard breaks)
- Line break at word boundaries
- Indent preserved on wrapped lines

## File Structure

Daily notes are created as `YYYY-MM-DD.md` directly in `~/notes` (no subfolder).
