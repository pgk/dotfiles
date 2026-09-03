# Handoff: Ariadne notes tooling session

**Status as of 2026-09-02.** Session-closing summary, not an open task — the
next session decides what's next. Written to be read cold.

## Goal

Extend the Ariadne notes-vault tooling (formerly named `notes-*`/`Obsidian*`,
renamed to `ariadne-*`/`Ariadne*` before this session — see below) with three
things the user asked for in sequence: a structural "notes that should be
split" signal, an Ollama model-setup helper, and free-text semantic search.

## What shipped, in order

1. **`ariadne-embed-setup`** — ensures `ariadne-similar`'s Ollama model is
   pulled, `--check` for status only. `doc/plans/PLAN-0006-splittable-notes-and-embed-setup.md`.
2. **Splittable-note detection** — `ariadne-graph`'s report gained a third
   node-level category (`[SPLIT]`), a heuristic only, no LLM: a note needs 3+
   `##` sections or 1200+ words, and must *not* itself act as a map of
   content (out-degree ≥ 8 vetoes it). Same plan doc as above.
3. **`:AriadneHelp`** (`<leader>oh`) — opens `ariadne.md` from a path computed
   off `commands.lua`'s own location.
4. **A README** for `base/nvim/nvim/lua/plugins/ariadne/` (file-by-file
   breakdown, pointers to the doc and dev rules).
5. **Semantic search** — `ariadne-similar --search "phrase"`, a fourth mode
   grouped by cluster (a free-text query has no cluster of its own to rank
   crossing-vs-within, unlike the target-note mode). `:AriadneSearch`
   (`<leader>oq`). `doc/plans/PLAN-0007-semantic-search.md`.
6. **CLAUDE.md cleanup** (this session's last step, prompted by the user:
   *"decisions live in code, docs live in readmes and helpfiles"*) —
   `ariadne/CLAUDE.md` had the same reasoning (duplicate thresholds, scan
   times, cluster-grouping rationale) written out fully in three places
   (`ariadne.md`, `bin/CLAUDE.md`, `ariadne/CLAUDE.md`). Consolidated: the
   Python-tool *why* now lives once in `bin/CLAUDE.md`; `ariadne/CLAUDE.md`
   keeps only Lua-side architecture facts and points at `bin/CLAUDE.md`
   instead of re-explaining. Also trimmed the Folgezettel section to its two
   decisions (reject-don't-half-parse; ids come from filenames not an index)
   instead of restating the grammar `folgezettel_spec.lua` already pins.
   Fixed `README.md`'s file table, which was missing `search.lua`/`cli.lua`.

## Decisions made, one line each

- Heuristic-only splitting, no LLM — see `[[project-notes-vault-llm-decisions]]`
  (auto-memory): an earlier session already closed "LLM note splitting" as
  "not surface-determinable." Re-litigating this without new information
  would be a mistake — check that memory before anyone proposes an LLM step
  for this feature again.
- Search groups by cluster rather than ranking crossing-vs-within, because a
  free-text query has no cluster of its own — confirmed with the user before
  building.
- `--search`/`--per-cluster`/`--duplicates`/`--dup-min` etc. all extend
  `ariadne-similar`'s existing multi-mode CLI rather than becoming new tools —
  matches this repo's own stated precedent ("extend, don't add a new tool").
- Commit messages in this repo carry no `Co-Authored-By`/Claude attribution —
  explicit user correction mid-session, now saved as
  `feedback-no-commit-attribution` (auto-memory).

## State

**Done, reviewed (`code-reviewer` + `security-reviewer` in parallel, findings
fixed and mutation-verified), and committed:** items 1, 2, 3, 4, 5 above —
`master` at `e3b3fee` and earlier. **Done but not yet committed:** item 6, the
CLAUDE.md/README cleanup — pure prose edits, no code, nothing to test.

**Not pushed.** `master` is ahead of `origin/master`; a local hook blocks
`git push` on protected branches unconditionally, so the user runs it
manually (`! git push`).

## How to verify

```sh
cd bin && for f in *_test.py; do printf "%-34s " "$f"; python3 "$f" 2>&1 | tail -1; done
# Expect: OK on all 16 files (or more, if a later session adds suites)
```

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/utils_spec.lua"
# Expect: 30 successes, 0 failures
```

Real end-to-end smoke test (needs Ollama running, `ariadne-embed-setup --check`
first): `ariadne-similar --search "some phrase" base/nvim/nvim/lua/plugins/ariadne/dev-vault`.

## Reference, not duplicated here

- `doc/plans/PLAN-0006-splittable-notes-and-embed-setup.md` and
  `doc/plans/PLAN-0007-semantic-search.md` — full design + what review
  changed, including the exact mutation-testing findings.
- `base/nvim/nvim/lua/plugins/ariadne/README.md` — file-by-file map.
- `bin/CLAUDE.md`, `base/nvim/nvim/lua/plugins/ariadne/CLAUDE.md` — dev rules,
  now the split described above.
- Auto-memory (`~/.claude/projects/-Users-pgk-dotfiles/memory/`):
  `project-notes-vault-llm-decisions`,
  `feedback-check-removed-plans-before-designing`,
  `feedback-no-commit-attribution`.

## Open items

- Docs cleanup (item 6) needs a commit.
- `git push` needs the user to run it.
- Nothing else queued. This was a "build what's asked, ship it" session, not
  a plan with remaining phases.

## Suggested skills for the next session

`/done` before calling anything "finished" here — it owns the review gate and
caught real bugs both times it ran this session (a header regex crossing
blank lines, an unpinned veto boundary, a dims-mismatch traceback, a bypassed
`main()` dispatch in tests). Check auto-memory before proposing an LLM-based
feature for this vault, or before assuming a `doc/plans/` file currently on
disk is the whole history — completed ones get deleted (`git log` finds them).

## Next action

Commit the docs cleanup (item 6), then this file has done its job — the
session can be `/clear`ed.
