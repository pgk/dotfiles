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
- CLI smoke tests (`notes-graph`, `notes-deadlinks`): pass `./dev-vault` (or a
  temp dir) as the vault argument explicitly — never rely on the `~/notes`
  default.
- Automated tests: build vaults with `tempfile.TemporaryDirectory()`, as the
  existing `*_test.py` files already do.
- Delegated subagents don't inherit this file automatically — brief them
  explicitly not to touch `~/notes`, and to use `./dev-vault` or a temp dir.
- If a real-vault run is ever genuinely necessary to verify something, ask
  the user first — don't assume it's fine.

## `dev-vault/`

A small, permanent, synthetic notes fixture: six files covering the cases
both `:ObsidianGraphHealth` and `:ObsidianDeadLinks` care about — a
well-connected hub, sparse notes (1-2 links), an orphan (zero links), and a
note with two dead links (one with a fuzzy-matchable typo, one with no
match). None of its content is derived from or related to the user's real
notes. Don't add a `README.md` or any other extra file inside `dev-vault/` —
every `.md` file there is scanned by the graph/dead-link tools, so an
unrelated file would skew their output.
