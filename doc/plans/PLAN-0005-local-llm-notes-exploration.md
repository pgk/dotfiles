# Handoff: exploring local LLMs for the notes vault

Written at the end of the session that shipped `notes-similar`
([[PLAN-0004-semantic-similar-notes]]), for a fresh session with no memory of it.

## What the next session is being asked to do

Two things, both exploratory — **no implementation was agreed**:

1. **Explore further ways local Ollama models could aid the notes workflow.**
   Broader than embeddings; the user has now seen embeddings work and wants the
   rest of the space.
2. **Research how Zettelkasten-style note-taking specifically benefits from local
   LLMs.** Web research expected. This is a real Zettelkasten (see below), not a
   generic note pile, so "AI second brain" listicles are mostly noise — look for
   what practitioners actually keep using.

Start with discussion and research, not code — last session's discuss, agree the
shape, then build worked well.

## Machine and runtime (verified, end of session)

| | |
|---|---|
| Hardware | Apple M3, 24 GB RAM |
| Ollama | 0.33.2, server on `localhost:11434` |
| Models pulled | `embeddinggemma:latest` only (621 MB) |
| Python | 3.14.7 (`math.sumprod` available; **numpy is not installed**) |
| Node | **absent** — no `node`/`npm`/`bun` on PATH; user was installing nvm |

Budget note: embeddings cost ~0.5 GB resident. A `gpt-oss-20b`-class model is
~14 GB and a Qwen3 27B ~17.5 GB, so a chat model competes with everything else
on a 24 GB machine. This shaped the last session's "embeddings, not an LLM"
decision and should be re-examined honestly rather than assumed.

## The vault (profiled last session — do not re-scan to confirm)

| | |
|---|---|
| Path | `~/notes` (private) |
| Size | 3,035 notes, 91 MB, ~537k words, ~177 words/note |
| Style | Numbered Zettelkasten: `1001a1`, `50g`, `80b`, plus `00 Dashboard` / `01 Top Of Mind` hubs |
| Languages | English **and Greek** — rules out English-only models |
| Frontmatter | 1,913 of 3,035 have it; **1,122 do not** |
| Editor | Neovim + obsidian.nvim, custom workflow in `base/nvim/nvim/obsidian-workflow.md` |

## Hard rule — read this before running anything

`bin/CLAUDE.md` and `base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` forbid
reading, scanning, or pointing any command at `~/notes` during development. Use
`base/nvim/nvim/lua/plugins/obsidian/dev-vault` (synthetic, 6 notes) or a
`tempfile` dir.

Violated twice historically, most recently **in the session that wrote this
file**: a zsh loop passed `"--index --exclude drafts/*"` as one unsplit word, it
landed as the target positional, and the vault fell back to its `~/notes` default
— 3,035 notes read, nothing uploaded. The fix removed the implicit default
entirely. Two lessons: **zsh does not word-split unquoted `$var`**, and a
"low-risk" default-path finding from a reviewer deserved more weight than it got.

## What already exists

Three CLI tools in `bin/`, all stdlib-only, all surfaced through fzf-lua pickers:

- `notes-graph` — orphan / sparsely-connected notes (`<leader>og`)
- `notes-deadlinks` — dead wikilinks with fuzzy candidates (`<leader>oD`)
- `notes-similar` — **new** — semantically similar but *unlinked* notes
  (`<leader>oS`; `<C-y>` inserts the link). Supporting modules
  `notes_embed_cache.py` and `notes_embed_client.py`.

`notes-similar` is built and the real vault **is indexed**: 3,035 notes, 768
dims, 9.3 MB, cache at `~/.cache/notes-similar/<hash>/` mode `0700`/`0600`.
User's verdict after first use: *"seems to work ok"*. 160 tests across 6 suites.

Its design constraints, which any sibling tool should probably inherit: no
implicit vault default (`$NOTES_VAULT` or an argument), loopback-only embedding
endpoint unless `--allow-remote-endpoint`, an egress announcement before any
upload, and graceful degradation to an empty result when no server is running.

## Ideas raised last session but NOT built

From the opening discussion; the user picked `notes-similar` first and these were
left. They are candidates, not commitments — re-litigate freely.

- **Relevance-based daily review.** `:ObsidianDailyReview` currently injects 5
  **random** notes. Embedding `01 Top Of Mind` and pulling nearest neighbours
  would make review track current thinking. Cheap: the index already exists.
- **Frontmatter backfill for the 1,122 notes without it.** The one job where a
  generative model clearly beats embeddings, and a one-time batch, so slow is
  fine. Must write proposals to a review file, never auto-apply. Related: tag
  hygiene — `00 Dashboard` has a duplicated `Note` tag, so there is likely more.
- **Voice capture.** Parakeet-TDT v3 on Apple Silicon is roughly 6× faster than
  Whisper Large v3. Only worth it if the user captures away from the keyboard —
  **this was never confirmed, ask before designing around it.**
- **Chat-with-your-vault RAG.** Actively deprioritized last session and the user
  did not push back: they have 3,000 atomic notes they wrote themselves and a
  working graph, so retrieval is the value and a chat wrapper mostly adds
  hallucination surface. Revisit only with a reason.

## Open questions to put to the user

- **Cross-lingual quality is unverified.** `embeddinggemma` was chosen because
  it is multilingual, but ranking was only ever tested on six synthetic English
  notes. Whether Greek and English notes place sensibly *relative to each other*
  is unknown. Ask what the first week of `<leader>oS` looked like — if
  cross-language hits are noise, that is a model swap (`NOTES_EMBED_MODEL` +
  `--rebuild`), not a code change.
- **Do the top hits read as connections worth making, or just shared vocabulary?**
  This is the question that decides whether to build more of this kind of thing.
- `bin/mknote` writes to `~/Sync/notes`, while obsidian.nvim and all three CLI
  tools use `~/notes`. Flagged twice, never resolved — probably stale.

## Loose ends in the repo

- `master` is **2 commits ahead of `origin/master`** — not pushed.
- Local branch `notes-similar` is merged and can be deleted.
- `base/nvim/nvim/lazy-lock.json` was modified *before* that session and is still
  unstaged. Not ours; left alone deliberately.
- `deadlinks.lua` has the same unsanitized `rel` field that was fixed in
  `similar.lua` — a known one-line fix, deliberately deferred.
- Opening any markdown buffer errors with
  `Error running markdownlint-cli2: ENOENT`. Cause: LazyVim's
  `lazyvim.plugins.extras.lang.markdown` extra wires `markdownlint-cli2` into
  `nvim-lint`, and it is an npm package with no Node runtime installed. Fix after
  nvm: `npm install -g markdownlint-cli2` or `:MasonInstall markdownlint-cli2`.
  Pre-existing and unrelated to the notes tooling.
