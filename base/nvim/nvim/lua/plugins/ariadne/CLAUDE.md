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

## Why similar/duplicates/search are separate Lua files

Three commands share the `ariadne-similar` CLI backend and one embedding
index, but each gets its own Lua file rather than branching inside
`similar.lua`. The *why* behind what each mode actually does — the embedded
text, the duplicate thresholds, the cluster grouping, the scan-time numbers —
lives in `bin/CLAUDE.md`, next to the Python that implements it; this section
only covers the Lua-side reason for the file boundary:

- `duplicates.lua` is async for a reason beyond the embedding round trip: its
  scan is every-pair and a warm cache does not shorten it (numbers in
  `bin/CLAUDE.md`). Don't fold it into `similar.lua`, and don't make a query
  pay for it.
- `search.lua` accepts an argument or prompts for one, the same fallback
  `commands.rename` already uses.
- Both mirror `similar.lua`'s async pattern (`vim.system`, never `:wait()`)
  and both go through `cli.lua`'s shared `decode`/`header_for`/`relative`
  rather than `utils.run_ariadne_tool` — see "Talking to the CLI tools" above
  for why `similar.lua` opts out of that helper, which applies here too.

## Deleting notes

`:AriadneDelete` is the only irreversible-looking command here, so it is a soft
delete: the note moves to `<vault>/.trash/`.

That works only because **every** vault walker skips dot-prefixed directories,
and there are two sets: `ariadne_common.iter_markdown_files` on the Python side,
and `find_note_file` / `list_note_files` / `grep_note_files` in `utils.lua`,
which shell out to `find` and `grep` and needed `DOTDIR_PRUNE` and
`--exclude-dir=.*` added. They didn't have it at first, so a trashed note came
back as a random note, as a backlink in the panel, and as a live link blocking
the next delete. Both sides are now pinned by tests — `ariadne_common_test.py`
and the two `delete_spec.lua` cases at the end. Don't add a fourth walker
without the skip.

Two rules it must keep:

- **Resolve links, don't match text.** `wikilinks.key()` mirrors
  `ariadne_common.resolve_link` — basename, no anchor, lowercased — so
  `[[Dir/A-Note#Top]]` counts as a link to `a-note`. `commands.rewrite_links`
  used to compare the raw bracketed text and so missed the path and anchor
  forms; since `rename` deletes the original, those became dead links, and it
  now goes through `wikilinks.retarget`. `utils.get_backlinks` still compares
  the bracketed prefix — survivable for a sidebar, not for a delete gate, which
  is why `delete.linking_notes` does not reuse it. In both, the grep is only a
  prefilter and searches the bare name, not `[[name`, so those forms reach the
  exact check at all.
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

`utils.vault_child(name, base)` contains a *name* within its `base`; it does
not check the base. That is the caller's job, and it is a real obligation, not
paperwork: `branch.lua` discharges it from a path already through `in_vault`,
but `place.lua` builds its base from a note path arriving in `ariadne-similar`'s
JSON, so it calls `in_vault` on that path first. Without it the guard rests
entirely on a property of *another process* — `ariadne_common.iter_markdown_files`
realpath-checks every note it yields, so a path outside the vault cannot come
back today — and what rests on it is a write followed by deleting the original.
A relative base is enough to break it: `vault_child("x", "rel")` returns
`rel/x.md`, which lands under nvim's cwd. Found by review; pinned by
`place_spec.lua`.

`commands.smart_follow_link` is the one place that correctly does not use it. It
compares a path it just built from `utils.vault_path` against `utils.vault_path`,
so both sides are unresolved and consistent, and a symlinked vault does not
affect it. Its check is lexical (`vim.fs.normalize` collapses `..` without
touching symlinks), which is what stops `[[../../etc/passwd]]`; a symlinked
*directory inside* the vault could still be followed out, which is exotic enough
to be left alone deliberately rather than overlooked.

## Folgezettel ids

`folgezettel.lua` is the whole grammar (pure; `folgezettel_spec.lua` pins
every case, including the carries — read there for the mechanics, not here).
Two decisions worth knowing before touching it:

- `segments()` **rejects** anything that is not a clean digit/letter
  alternation, rather than half-parsing it — that refusal is how a note like
  `hub-note` opts out of the scheme (`split()` returning `nil` is the signal,
  not an error case). Letters never carry into a new digit segment, because
  the alternation *is* the depth; "fixing" that would break it.
- `branch.lua` reads taken ids from filenames rather than from any index, so
  a note created outside the editor still reserves its number — but the new
  note's link back to its parent is the only thing telling `ariadne-graph`
  they are related. A branched note with no link is an orphan by that
  measure, the id alone does not count.
- `branch.taken_ids()` is that scan, and `place.lua` shares it rather than
  copying it. Two scans that agree today are two scans, and only one of them
  gets edited.
- **`place.lua` answers a question the grammar cannot.** `folgezettel.lua` can
  say what a child of `1a2` is called; nothing in it can say that *this* note is
  one. So `:AriadnePlace` asks `ariadne-similar` instead and keeps only the
  neighbours whose own names parse as an id. Three decisions in it:
  - It sends `--all --no-bridge -n 50`, which is **not** `:AriadneSimilar`'s
    query. Bridge-first ordering deliberately promotes the structurally novel
    pair (see `ariadne_ranking._bridged`), and a parent should be the *nearest*
    note, not the most surprising one. A note already linked to its natural
    parent is the common case here rather than one to filter out, so it is
    marked `[linked]` instead of dropped. The limit is wide because the id
    filter is invisible to the ranking: in the vault this command exists for,
    most notes have no id, so a default ten can be ten notes naming no place.
  - Rows are deduplicated **by proposed id**. `sibling of 1a1` and `sibling of
    1a2` both walk to the first free id in the 1a line, and the losing row would
    name a parent the result does not sit next to.
  - The id grammar cannot distinguish "elaborates" from "continues", so both a
    child and a sibling row are offered per neighbour and the wording carries
    the difference. Don't collapse them to one.
  - **A placed note gets the parent link too, but conditionally.** The invariant
    two bullets up applies here exactly as it does to `branch.lua`: the id
    implies the relationship, `ariadne-graph` counts wikilinks, so a placed note
    with no edge to its parent is an orphan by the measure that matters. It is
    conditional because a note being *placed* is not new — it may already
    reference its parent, and the ranking already said so. `linked` in the
    payload covers either direction, so a parent linking *to* the note counts:
    the edge exists and a second one adds nothing. The wording follows
    `branch.lua`'s — "Branched from" for a child, "Continues" for a sibling.
    Without this the two commands contradicted each other, which is how review
    found it.
  - `taken_ids` is read after the async round trip but still before the picker
    and the blocking title prompt, so a note claiming that id in *another*
    directory in the interim would give two notes one id (`commands.rename`
    catches a collision only in the destination directory). Left as is
    deliberately: `branch.lua` has the identical window by the same
    ids-on-disk-are-the-truth design, and closing it here alone would cost a
    second full-vault `find` per placement to cover seconds of a single-user
    editor.

The async guard in `apply` compares the buffer's **name**, not its handle.
`nvim_win_get_buf(win) ~= buf` only proves the same buffer is displayed, and
`:saveas` / `:file` rename a buffer while keeping its handle — so both handle
checks passed while `commands.rename` destroyed a different file than the one
the ranking, the id and the title prefill all described, with no warning. It
also subsumes "the note gained an id while the picker was open": gaining one
means being renamed, and a name still equal to `origin.path` has a stem
`refusal` already cleared. Don't add a second id check for that — it is
unreachable, which a test written for it quietly demonstrated by passing on the
name check instead.

## Renaming: write before you retarget

`commands.rename` writes the destination **before** rewriting the vault's links
at it, and the order is load-bearing. The write is the step that can still fail
— a destination directory that has gone away throws E212 — and it used to run
last, so a failure left the original note in place with every `[[link]]` to it
already pointing at a name that did not exist: a vault-wide dead-link event with
no rollback. `update_frontmatter_id` has to precede the write, because
`utils.write` writes the *buffer*. `commands_spec.lua` pins it, and that test
is the one that caught the ordering being silently reverted during review.

`utils.write` returns false rather than letting a failed write propagate: E212
is thrown for a destination directory that has gone away, and `place.lua` calls
this from an fzf-lua action, where a traceback lands on the user instead of a
message. `utils.vault_child` also normalizes its `base` — the containment test
compares against `base .. "/"`, so a base with a trailing slash never matched
its own normalized output and refused every name. Not reachable through `:h`,
but `M.vault_path` is whatever `obsidian.nvim` was configured with. Both are
pinned in `utils_spec.lua`, which now covers `vault_child` at all.

`rename` also builds its destination with `utils.vault_child`, not a
concatenation. It previously concatenated, so `:AriadneRename ../../elsewhere`
placed the note outside the directory being renamed in — and rename deletes the
original, so nothing was left behind.

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

`cli.lua` holds what the two async tool callers share — the payload decoder, the
picker header and the vault-relative path — while `utils.run_ariadne_tool` stays
the synchronous runner. The split is deliberate: `similar.lua` and
`duplicates.lua` order their argv differently and only one announces itself, so
an async *runner* at two callers would be a flag per difference. Sharing the
decoder cost nothing and closed a real gap — `similar.lua`'s `header_for` used
bare `or 0` where `graph.lua`'s documented that `vim.NIL` throws.

`utils_spec.lua` also pins `in_vault` against a real symlinked tempdir vault,
including the unwritten-buffer case and a sibling directory whose name merely
starts with the vault path.

`folgezettel_spec.lua` pins the id grammar including every carry;
`branch_spec.lua` drives both commands against tempdir vaults with the title
prompt stubbed, covering id allocation, the parent link, the subdirectory
placement, and each refusal.

`commands_spec.lua` covers `commands.rename`, which had no coverage until it
grew a destination directory: the move, the escape refusal, the existing-target
refusal, and the write-before-retarget ordering above.

`place_spec.lua` drives `:AriadnePlace` end to end against tempdir vaults —
argv, the row set, id allocation, the dedupe, the move beside the parent, the
link retarget, and each refusal. It stubs `vim.system` **only** for
`ariadne-similar`: the `find` and `grep` beneath `branch.taken_ids` and
`commands.rename` go through to the real one, because which ids are taken and
what links at the note are the two things the command must get right, and a stub
there would only assert the fixture back at itself.

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
