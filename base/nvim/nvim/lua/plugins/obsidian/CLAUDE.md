# Obsidian plugin — development rules

This directory implements the user's custom Obsidian-style notes workflow for
Neovim (`obsidian-workflow.md` documents the end-user side). The real vault
lives at `~/notes` and is private.

## Never touch the real vault during development

When writing, testing, or debugging anything in this directory — or the
`notes-graph` / `notes-deadlinks` CLI tools in `bin/` that back it — never
read, scan, or point a command at `~/notes`, not even "just to check" or to
reproduce a bug. See "How to apply" below for what to use instead.

**Why:** a past session accidentally scanned the real vault once, via an
argument-parsing bug (`--exclude` swallowing the vault positional), revealing
a note count and one filename before it was caught and fixed. Since then this
is a hard rule, not a judgment call.

**How to apply:**
- Manual/interactive testing (e.g. checking a new `:Obsidian*` command in
  Neovim): temporarily point `Obsidian.dir` / the workspace path at
  `./dev-vault`, never at `~/notes`.
- CLI smoke tests (`notes-graph`, `notes-deadlinks`, `notes-similar`): pass
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

`activity.lua` / `notes-graph --since`, `notes-graph --neglected`, and the daily
note's "on this day" fallback all treat mtime as "the user edited this". That
held when it was checked (29 of 3,037 notes in a week), but it is an assumption about
the user's sync setup, not a property of the code. If it ever stops holding, the
window fills with untouched notes and the feature is worthless — re-measure before
building anything else on top of it.

## Lua tests

`utils_spec.lua` covers `utils.sanitize` and `utils.edit` — the two helpers standing
between a hostile note filename and the editor, both of which were wrong until a
review caught them. Run it with `:PlenaryBustedFile %`, or headless:

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/obsidian/utils_spec.lua"
```

`anniversary_spec.lua` covers the "on this day" date logic behind the daily-note
section. Both its functions are pure, so it needs no vault — run it the same way,
swapping the filename.

The picker row builders (`describe`, `describe_cluster`, `header_for`) are still
module-local and untested; export them if you need to pin their behaviour.

## `dev-vault/`

A small, permanent, synthetic notes fixture. None of its content is derived
from or related to the user's real notes.

Node-level cases, for `:ObsidianGraphHealth` and `:ObsidianDeadLinks`: a
well-connected hub (`hub-note`), sparse notes with 1-2 links, an orphan with
zero (`orphan-note`), and a note with two dead links — one fuzzy-matchable
typo, one with no match (`broken-link-note`).

Cluster-level cases, for the community detection in `notes_cluster.py`:

- **Three link communities.** The original project/meeting cluster around
  `hub-note`; a second, `cluster-b-*`, with its own hub; and `hubless-*`.
- **A bridge.** `bridge-note` is the sole path between all three — an
  articulation point, and the structural-hole case that cluster-crossing
  ranking exists to find.
- **A cluster with no hub.** `hubless-one`..`hubless-eight` form a ring where
  every note has degree 2, so no note links to enough of the cluster to be its
  entry point (`notes-graph` reports coverage 2/7). **Don't shrink the ring**,
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
harbours, pottery) so `notes-similar` separates them too, not just the link
graph.

**Adding files.** More *synthetic notes* are fine and expected — the fixture
grew for exactly this reason, and it will grow again. Don't add a `README.md`
or any other non-note file: every `.md` file here is scanned by the tools, so
one that isn't a note skews their output. When you add notes, keep the
existing fixtures' degrees and dead links intact (adding an inbound link to
`hub-note` is safe; adding one to a note documented as sparse is not) and
update this section. Adding links inside the harbour ring would give it an
entry point and silently disarm the missing-hub fixture.
