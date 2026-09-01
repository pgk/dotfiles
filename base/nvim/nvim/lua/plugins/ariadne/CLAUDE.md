# Ariadne — development rules

This directory implements Ariadne, the user's wikilink-based notes workflow for
Neovim, layered on `obsidian.nvim` (`ariadne.md` documents the end-user
side). The real vault lives at `~/notes` and is private.

## Never touch the real vault during development

When writing, testing, or debugging anything in this directory — or the
`ariadne-graph` / `ariadne-deadlinks` CLI tools in `bin/` that back it — never
read, scan, or point a command at `~/notes`, not even "just to check" or to
reproduce a bug. See "How to apply" below for what to use instead.

**Why:** a past session accidentally scanned the real vault once, via an
argument-parsing bug (`--exclude` swallowing the vault positional), revealing
a note count and one filename before it was caught and fixed. Since then this
is a hard rule, not a judgment call.

**How to apply:**
- Manual/interactive testing (e.g. checking a new `:Ariadne*` command in
  Neovim): temporarily point `Obsidian.dir` / the workspace path at
  `./dev-vault`, never at `~/notes`.
- CLI smoke tests (`ariadne-graph`, `ariadne-deadlinks`, `ariadne-similar`): pass
  `./dev-vault` (or a temp dir) as the vault argument explicitly. None of the
  three has a `~/notes` default any more — they refuse to run without a named
  vault — but name it deliberately rather than leaning on that refusal.
- Automated tests: build vaults with `tempfile.TemporaryDirectory()`, as the
  existing `*_test.py` files already do.
- Delegated subagents don't inherit this file automatically — brief them
  explicitly not to touch `~/notes`, and to use `./dev-vault` or a temp dir.
- If a real-vault run is ever genuinely necessary to verify something, ask
  the user first — don't assume it's fine.

## `--since` and modification times

`activity.lua` / `ariadne-graph --since`, `ariadne-graph --neglected`, and the daily
note's "on this day" fallback all treat mtime as "the user edited this". That
held when it was checked (29 of 3,037 notes in a week), but it is an assumption about
the user's sync setup, not a property of the code. If it ever stops holding, the
window fills with untouched notes and the feature is worthless — re-measure before
building anything else on top of it.

## Talking to the CLI tools

`utils.run_ariadne_tool(tool, extra_argv, required, opts)` is the one synchronous
path from Lua to `bin/`: it builds `{tool, vault, extras..., --json}`, sanitizes
stderr, and refuses a payload missing any `required` key so the failure lands
there rather than at the indexing site. `graph.lua`, `activity.lua`,
`deadlinks.lua` and `daily.lua` all go through it — four hand-rolled copies
before, one of which forwarded stderr to `vim.notify` unsanitized.

`similar.lua` is deliberately **not** routed through it: it runs asynchronously,
puts the current note before the vault, and reports its own `error` field. Don't
"finish the job" by folding it in.

`utils.sample(list, count)` is the shared random-unique picker, and `utils.lua`
seeds `math.random` once at load from `hrtime()` — `os.time()` has one-second
resolution, so two commands run in the same second replayed the same draw.

## What `ariadne-similar` embeds

`note_text()` embeds the note *name* followed by the body, with every
`[[wikilink]]` flattened to the words a reader sees
(`ariadne_common.wikilink_display`). Both matter: body-only embeddings made
short notes with descriptive titles hard to retrieve, and an unflattened link is
punctuation and a slug where the reader sees two words of meaning. Changing
either changes every note's content hash, so it forces a full re-index — the
`--max-refresh` guard turns that into an honest "run --index" message rather
than a silent multi-minute upload, which is the behaviour to keep.

`duplicates.lua` / `ariadne-similar --duplicates` is a second question over the
same index, and it needs the **title** signal as well as the embedding one. The
numbers and the reasoning live in `bin/CLAUDE.md`; the short version is that
cosine alone cannot separate "the same note twice" from "a neighbouring idea",
and the latter is what `:AriadneSimilar` already reports. Both thresholds are
borrowed calibration from another vault, so treat a bad hit rate as a reason to
re-tune `--dup-min` / `--dup-title-min`, not as a bug.

The picker is async for a second reason beyond the embedding round trip:
the scan itself is every-pair, 48s at 3040 notes — and a warm cache does not
shorten it.
Don't fold it into `similar.lua`, and don't make a query pay for it.

## Deleting notes

`:AriadneDelete` is the only irreversible-looking command here, so it is a soft
delete: the note moves to `<vault>/.trash/`, which `iter_markdown_files` skips
along with every other dot-prefixed directory. Nothing else had to change for it
to disappear from the graph, the index and the pickers.

Two rules it must keep:

- **Resolve links, don't match text.** `wikilinks.key()` mirrors
  `ariadne_common.resolve_link` — basename, no anchor, lowercased — so
  `[[Dir/A-Note#Top]]` counts as a link to `a-note`. `utils.get_backlinks` and
  `commands.rewrite_links` both compare the raw bracketed text instead and miss
  the path and anchor forms. That is survivable for a sidebar and not for
  deciding whether a delete needs confirming, which is why neither is reused
  here. The grep is only a prefilter; it searches the bare name, not `[[name`,
  so those forms reach the exact check at all.
- **Ask `utils.in_vault(path)`, never `vim.startswith(path, vault)`.** See
  "Is this path in the vault?" below.

## Is this path in the vault?

`utils.in_vault(path)` — and nothing else. nvim reports a buffer's name with
symlinks resolved, so a vault configured through one shares no prefix with its
own notes: configured as `/var/...`, its buffers arrive as `/private/var/...`,
and `~/notes -> ~/Dropbox/notes` behaves the same. Three gates compared the two
raw and so refused every note in a symlinked vault — `:AriadneSimilar`, the
links panel, and the `formatexpr` that stops `gw` breaking a `[[wiki link]]`
across lines. `utils.resolve` also resolves the *parent* when the file itself is
not on disk, so a new note in an unwritten buffer still counts as inside.

`commands.smart_follow_link` is the one place that correctly does not use it. It
compares a path it just built from `utils.vault_path` against `utils.vault_path`,
so both sides are unresolved and consistent, and a symlinked vault does not
affect it. Its check is lexical (`vim.fs.normalize` collapses `..` without
touching symlinks), which is what stops `[[../../etc/passwd]]`; a symlinked
*directory inside* the vault could still be followed out, which is exotic enough
to be left alone deliberately rather than overlooked.

## Lua tests

`utils_spec.lua` covers `utils.sanitize` and `utils.edit` — the two helpers standing
between a hostile note filename and the editor, both of which were wrong until a
review caught them. Run it with `:PlenaryBustedFile %`, or headless:

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/utils_spec.lua"
```

`anniversary_spec.lua` covers the "on this day" date logic behind the daily-note
section — `date_from_name` and `on_this_day` are pure, `entries_for` gets a
tempdir. Run it the same way, swapping the filename.

`utils_spec.lua` also covers `as_wikilink`, `sample`, `write` and
`run_ariadne_tool`; the last builds a fake tool on `$PATH` and asserts the argv
order every caller depends on.

`utils_spec.lua` also pins `in_vault` against a real symlinked tempdir vault,
including the unwritten-buffer case and a sibling directory whose name merely
starts with the vault path.

`wikilinks_spec.lua` pins the link grammar — resolution keys, display text and
unwrapping — against the path, anchor, alias and embed forms. `delete_spec.lua`
drives the whole delete against tempdir vaults with `Obsidian.dir` pointed at
them and `vim.fn.confirm` stubbed to a canned list of answers, covering the
confirm gate, cancellation, the unwrap, the `.trash/` collision suffix and every
refusal. Those two are the only command-level Lua coverage in the directory;
the pickers remain untested.

## Opening and writing paths

`vim.cmd("edit " .. fnameescape(path))` is banned here — `fnameescape` does not
escape a newline and `nvim_exec2` splits on one first, so the rest of a crafted
filename runs as an Ex command. Use `utils.edit(path)` and `utils.write(path)`,
which pass the path as an argument. `utils.write` returns false rather than
writing when the path is unusable, because `commands.rename` deletes the
original on the very next line. There is no `fnameescape` left in `lua/`; keep it
that way.

The picker row builders (`describe`, `describe_cluster`, `header_for`) are still
module-local and untested; export them if you need to pin their behaviour.

## `dev-vault/`

A small, permanent, synthetic notes fixture. None of its content is derived
from or related to the user's real notes.

Node-level cases, for `:AriadneGraphHealth` and `:AriadneDeadLinks`: a
well-connected hub (`hub-note`), sparse notes with 1-2 links, an orphan with
zero (`orphan-note`), and a note with two dead links — one fuzzy-matchable
typo, one with no match (`broken-link-note`).

Cluster-level cases, for the community detection in `ariadne_cluster.py`:

- **Three link communities.** The original project/meeting cluster around
  `hub-note`; a second, `cluster-b-*`, with its own hub; and `hubless-*`.
- **A bridge.** `bridge-note` is the sole path between all three — an
  articulation point, and the structural-hole case that cluster-crossing
  ranking exists to find.
- **A cluster with no hub.** `hubless-one`..`hubless-eight` form a ring where
  every note has degree 2, so no note links to enough of the cluster to be its
  entry point (`ariadne-graph` reports coverage 2/7). **Don't shrink the ring**,
  for three measured reasons: six is the arithmetic minimum, because a five-note
  cluster scores exactly 0.5 and is spared by the `>=` in `hubless_clusters`;
  seven makes Louvain pull `bridge-note` in, so the reported size stops matching
  the ring length and the assertions get confusing; and eight scores 0.286
  rather than 0.4, which is margin against the clustering shifting slightly.
  (Rings of four through eight all survive Louvain here — a *bare* ring splits
  into arcs, but this one has a denser neighbour, which changes that.)
- **A disconnected component.** `island-one`..`island-three` have no path to
  the rest of the vault — a component, as opposed to the single-note orphan.

Each cluster is given deliberately distinct vocabulary (planning, gardening,
harbours, pottery) so `ariadne-similar` separates them too, not just the link
graph.

Splittable-note cases, for `ariadne_splittable.py` (`ariadne-graph`'s "Splittable"
section): `splittable-candidate` is long and multi-section, links out to only
`hub-note`, and should be flagged. `splittable-index` links to exactly eight
`splittable-index-target-*` stubs, putting its out-degree exactly at the
`--max-out-degree` default (8) — the gate is `< max`, not `<=`, so this is the
boundary case proving the map-of-content veto fires and must not be flagged
despite having headers of its own. Keep the target count at exactly eight if
this fixture is ever edited.

**Adding files.** More *synthetic notes* are fine and expected — the fixture
grew for exactly this reason, and it will grow again. Don't add a `README.md`
or any other non-note file: every `.md` file here is scanned by the tools, so
one that isn't a note skews their output. When you add notes, keep the
existing fixtures' degrees and dead links intact (adding an inbound link to
`hub-note` is safe; adding one to a note documented as sparse is not) and
update this section. Adding links inside the harbour ring would give it an
entry point and silently disarm the missing-hub fixture.
