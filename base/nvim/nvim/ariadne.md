# Ariadne — the Neovim notes workflow

Ariadne is the custom Zettelkasten layer for Neovim, built on top of
[obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim). It owns the
`:Ariadne*` commands and the `bin/ariadne-*` CLI tools; obsidian.nvim underneath
it owns the vault plumbing and the `:Obsidian <subcommand>` form.

## Vault Location

`~/notes`

## Keybindings

### Global (available anywhere after startup)

| Key | Command | Description |
|-----|---------|-------------|
| `<leader>od` | `:AriadneDaily` | Open today's daily note (with template) |
| `<leader>or` | `:AriadneRandom` | Open a random note |
| `<leader>ol` | `:AriadneLinksPanel` | Toggle links panel sidebar |
| `<leader>os` | `:Obsidian search` | Search vault (fulltext) |
| `<leader>on` | `:Obsidian new` | Create a new note |
| `<leader>oi` | `:AriadneInsertLink` | Search vault and insert link at cursor |
| `<leader>ob` | `:Obsidian backlinks` | Backlinks in picker |
| `<leader>of` | `:Obsidian links` | Forward links in picker |
| `<leader>ot` | `:AriadneTransclusionToggle` | Toggle transclusion rendering |
| `<leader>oR` | `:AriadneRename` | Rename note and update all links |
| `<leader>og` | `:AriadneGraphHealth` | Find orphans, sparse notes, splittable notes, and clusters with no hub |
| `<leader>oa` | `:AriadneActive` | Notes touched recently, grouped by link community |
| `<leader>oh` | `:AriadneHelp` | Open this doc |
| `<leader>oD` | `:AriadneDeadLinks` | Find dead links and possible matches |
| `<leader>oS` | `:AriadneSimilar` | Find semantically similar but unlinked notes |
| `<leader>ou` | `:AriadneDuplicates` | Find duplicate and near-duplicate notes |
| `<leader>oX` | `:AriadneDelete` | Delete the current note, checking what links to it |

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
| `:AriadneRandom` | Open a random note from vault |
| `:AriadneLinksPanel` | Toggle the links panel sidebar |
| `:Obsidian search` | Fulltext search across vault |
| `:Obsidian new` | Create a new note |
| `:AriadneInsertLink` | Search and insert a `[[link]]` at cursor |
| `:AriadneDailyReview` | Add 5 random notes to today's daily note |
| `:Obsidian backlinks` | Show backlinks in picker (built-in) |
| `:Obsidian links` | Show forward links in picker (built-in) |
| `:AriadneTransclusionToggle` | Toggle inline transclusion rendering |
| `:AriadneRename [name]` | Rename current note and update all links |
| `:AriadneDaily [offset]` | Open daily note with template (offset: -1 = yesterday, 1 = tomorrow) |
| `:AriadneGraphHealth` | Find orphans, sparse notes, splittable notes, and clusters with no hub (picker) |
| `:AriadneActive [7d]` | Notes touched in a recent window, grouped by cluster (picker) |
| `:AriadneHelp` | Open this doc |
| `:AriadneDeadLinks` | Find dead links and possible matches (picker) |
| `:AriadneSimilar` | Find semantically similar but unlinked notes (picker) |
| `:AriadneSimilarIndex[!]` | Refresh the embedding index in the background (`!` rebuilds from scratch) |
| `:AriadneDuplicates [n]` | Find duplicate and near-duplicate notes (picker; `n` caps the "possible" band) |
| `:AriadneDelete` | Move the current note to `.trash/`, asking first if anything links to it |

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
  `ariadne-graph --neglected`. Three are sampled from the 50 best connected rather
  than taken in rank order, so the same notes do not reappear every morning.
  Absent if `ariadne-graph` is not on `PATH` (you get a warning instead).

Workflow:
1. `<leader>od` - Open/create today's note
2. Review the random notes, add thoughts
3. Use `<leader>oi` to insert links to related notes

## Renaming Notes

Use `<leader>oR` or `:AriadneRename` to rename the current note:
- Prompts for new name (pre-filled with current name)
- Renames the file
- Updates all `[[links]]` across the vault automatically

## Graph Health

Use `<leader>og` or `:AriadneGraphHealth` to find structural problems in the
vault, at two levels:
- Backed by the `ariadne-graph` CLI tool (`bin/ariadne-graph` in dotfiles). It reads
  only the link graph and note text — no embedding server, no network, no LLM
- **Per note:** orphans have zero `[[links]]` in or out; sparse notes are below
  the connection threshold (default: 3, see `ariadne-graph --help`); `[SPLIT]`
  rows are notes that have grown past one idea's worth of content — at least 3
  `##`/`###` sections, or 1200+ words for headerless sprawl — and aren't
  themselves acting as a map of content (8+ outbound links vetoes the flag).
  It's a structural signal only: no claim about where one idea ends, just
  that the note is long/multi-section and not an index. The `ariadne-graph` CLI
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
`:Ariadne*` ones are this config's own — they are ordinary user commands, so they
are unaffected by the plugin's `legacy_commands` deprecation, which is set to
`false` here. That setting drops obsidian.nvim's own `ObsidianXxx` aliases, which
is why nothing here is named that way any more.

## Recent Activity

Use `<leader>oa` or `:AriadneActive` to see what you have actually been working on.
Where graph health is an audit you run occasionally, this is a daily view:

- Backed by `ariadne-graph --since` (`ariadne-graph ~/notes --since 7d`). Takes a window
  like `7d`, `36h` or `2w`; `:AriadneActive 2w` passes it through, default `7d`
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

Use `<leader>oD` or `:AriadneDeadLinks` to find `[[wikilinks]]` that don't resolve
to any note:
- Backed by the `ariadne-deadlinks` CLI tool (`bin/ariadne-deadlinks` in dotfiles)
- Each dead link is shown with up to 3 fuzzy-matched candidate note names (or "no
  matches"), for the typo/rename case
- Results open in an fzf-lua picker, one row per `(note, dead link)` pair; select
  one to jump to the **referring note** so you can fix the link — not to the
  suggested match, since a wrong guess would silently take you to the wrong note

## Similar Notes

Use `<leader>oS` or `:AriadneSimilar` to find notes that are *about* the same
thing as the current one but aren't linked to it — the connection you meant to
make and forgot. Where `:AriadneGraphHealth` finds notes with too few links and
`:AriadneDeadLinks` finds links pointing nowhere, this finds the links that were
never made:

- Backed by the `ariadne-similar` CLI tool (`bin/ariadne-similar` in dotfiles), which
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
ariadne-similar --index ~/notes    # or: export NOTES_VAULT="$HOME/notes"
```

`ariadne-embed-setup` automates that first line: pulls the model if it's
missing, or with `--check` just reports whether it is. Ollama-only (shells
out to `ollama list`/`ollama pull`); on LM Studio or `llama-server`, pull the
model through that tool's own UI or CLI instead.

`embeddinggemma` is multilingual, which matters for the non-English notes in the
vault. Any OpenAI-compatible server works — point `NOTES_EMBED_URL` at LM Studio
or `llama-server` instead, and set `NOTES_EMBED_MODEL` to its model name.

The first index embeds the whole vault and takes a few minutes; everything after
that is incremental, since only notes whose text changed get re-embedded.

What gets embedded is the note's name, then its body with every `[[wikilink]]`
replaced by the words a reader sees — `[[working-memory|Working Memory]]` embeds
as `Working Memory`, not as brackets and a slug.

Changing that rule invalidates the whole cache at once, because every note's
content hash changes with it. Flattening the wikilinks did exactly that, so the
first `:AriadneSimilar` or `:AriadneDuplicates` after it lands will report the
vault as unindexed and ask for `:AriadneSimilarIndex`. That is the
`--max-refresh` guard doing its job rather than silently re-uploading the vault. Vectors
are cached in `~/.cache/ariadne-similar/` (mode `0600`, no note text — just paths,
hashes, and vectors), never inside the vault.

`:AriadneSimilar` re-embeds edited notes on the fly, but refuses to do a full
index from inside the picker — if a lot of notes are unindexed it says so and
asks you to run `:AriadneSimilarIndex` (or the CLI) instead. The CLI call is
async, so neither command blocks the editor.

If the embedding model is ever swapped for one with a different vector size,
`:AriadneSimilarIndex!` (or `ariadne-similar --index --rebuild <vault>`) discards
the cache and starts over.

Clustering itself needs no server and no index — it reads only the wikilink
graph. `ariadne-similar --no-bridge` turns the grouping off and ranks purely by
similarity.

### Where your notes go

To keep a subtree out of the index entirely, pass `--exclude` — `ariadne-similar
--index --exclude journal ~/notes`. It matches directory names as well as globs, is
case-insensitive, and warns if a pattern matched nothing, since a typo there would
silently upload the notes you meant to hold back.

`ariadne-similar` is the only tool in this workflow that sends note text off-process,
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

## Duplicates

Use `<leader>ou` or `:AriadneDuplicates` to find the same note written twice.
It reuses the same embedding index as `:AriadneSimilar`, but asks a different
question, and it needs **two** signals to answer it:

- A pair is a **candidate** when its embedding cosine is at least `0.80`
- A candidate is a **duplicate** when the two titles also agree — `difflib`
  similarity at least `0.85`. Below that it lands in *Possibly the same idea*

That second signal is the whole point. On a measured corpus the one genuine
duplicate scored 0.842 cosine and 1.000 on the title, while every other pair
above 0.80 cosine scored at most 0.430 on the title. Embedding similarity alone
cannot tell "the same note twice" from "two notes about neighbouring ideas" —
and the near-neighbours are exactly what `:AriadneSimilar` is already for.

So read the two sections differently: **Duplicates** is a merge list, and
*Possibly the same idea* is the wide, noisy band, capped by `-n` (default 10).
Numbered sibling stubs — `topic-1`, `topic-2` — will fill the duplicate list
legitimately, because they really are near-identical.

Rows name two notes. `<CR>` opens the left one, `<C-o>` the right, and `<C-v>`
opens both side by side, which is where a merge starts.

Both thresholds are borrowed calibration from another vault, not a measurement
of this one. Re-tune them on the CLI: `ariadne-similar --duplicates ~/notes
--dup-min 0.85 --dup-title-min 0.9`.

The scan compares every pair of notes with no index structure — about 48 seconds
at three thousand notes — which is why it is its own command and not something
`:AriadneSimilar` pays for on every query. An up-to-date index does not make it
quicker; it saves the embedding round trip, not the 4.6M comparisons. It runs
async, so the editor stays usable while it works.

## Deleting a Note

Use `<leader>oX` or `:AriadneDelete` on the note you have open. It is a **soft**
delete: the file moves to `<vault>/.trash/`, which every tool here skips because
it is dot-prefixed, so the note leaves the graph, the index and the pickers at
once but comes back with a single `mv`. A name already in `.trash/` is suffixed
rather than overwritten, so deleting `inbox.md` twice keeps both.

If nothing links to the note it goes straight to the trash. If something does,
you get the count and the linking notes first, defaulting to Cancel:

```
Delete 'bounded-rationality'?

3 link(s) in 2 note(s) point here:
  project-plan (2)
  reading-list (1)
```

Afterwards you are offered a cleanup: rewriting `[[bounded-rationality]]` to
plain `bounded-rationality` in those notes, so the vault is left with no dead
links. An alias is kept — `[[a-note|the other one]]` becomes `the other one` —
and links to every other note are untouched. Decline and the dangling links stay
for `:AriadneDeadLinks` to find.

What counts as a link is resolved properly rather than matched as text, so
`[[a-note]]`, `[[Dir/A-Note]]`, `[[a-note#Heading]]` and `![[a-note]]` all count,
while `[[a-note-elsewhere]]` and a bare mention in prose do not.

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
