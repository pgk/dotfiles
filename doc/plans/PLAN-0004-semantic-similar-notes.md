# Semantic similar-note detection

## Context

Third tool in the vault-health family, after [[PLAN-0001-notes-graph-health]]
(`notes-graph` + `:ObsidianGraphHealth`) and
[[PLAN-0003-dead-links-detection]] (`notes-deadlinks` + `:ObsidianDeadLinks`).

Both existing tools reason about links that **exist**: `notes-graph` finds notes
with too few, `notes-deadlinks` finds ones pointing nowhere. Neither sees the
opposite failure — two notes that belong together and were never linked, because
nothing in their text overlaps lexically. That decay mode needs meaning, not string
matching.

`notes-similar` embeds every note once, caches the vectors, ranks the vault against
a target by cosine similarity, then **subtracts the notes already linked** in either
direction, so every row is a connection that doesn't yet exist.

Decisions made with the user this session:

- **Embeddings, not a chat model.** The job is retrieval over notes the user wrote;
  a generative model would add a hallucination surface for no gain. This also keeps
  the resident cost at ~0.5 GB instead of ~14 GB on a 24 GB machine.
- **Stdlib only**, like `notes-graph` and `notes-deadlinks`. `urllib.request` for
  HTTP, `array` for vector storage, `math.sumprod` for the dot product. Measured:
  3,035 × 768-dim on Python 3.14 takes **28 ms** — numpy would buy nothing.
- **OpenAI-compatible `/v1/embeddings`**, defaulting to `http://localhost:11434/v1`
  (Ollama). The same code works against LM Studio or `llama-server`, so the tool
  isn't married to one runtime. Overridable via `NOTES_EMBED_URL` / `NOTES_EMBED_MODEL`.
- **Default model `embeddinggemma`** — multilingual, because a meaningful slice of
  the vault is Greek. An English-only embedder (`bge-large-en`) would go blind there.
- **Degrade to nothing, never to a stack trace.** No server, model, or index
  produces a warning and an empty result set. Requested by the user, and the primary
  path today since no embedding runtime is installed yet.
- **Manual `--index`, auto-refresh on query.** A first index of 3,035 notes is a
  multi-minute job and must never block an fzf picker. Queries re-embed only notes
  whose content hash changed, and refuse (with a message) if more than
  `--max-refresh` are missing.
- **Unlinked-only by default**, `--all` to include existing links. For a hub note
  the raw top-10 would otherwise be links already made.
- **Picker opens the note; `<C-y>` inserts the `[[link]]`.** Default matches the
  select → edit behaviour of the two existing pickers, so the target can be read
  before it's linked.
- Per [[feedback_notes_vault_privacy]]: built and tested against **synthetic**
  vaults only. `~/notes` is never read during development, and no live embedding
  server is required to run the test suite.

## Revised after review

The first implementation was reviewed by independent code and security passes,
which changed four things worth recording:

- **The cache could pair one run's `index.json` with another run's `vectors.f32`**
  (both reviewers, independently). The mapping was positional across two separate
  `os.replace` commits, so an interleaved `:ObsidianSimilarIndex` and picker
  refresh could load every note against its neighbour's vector — silently, since
  the hashes still matched. `index.json` now names the generation-stamped vector
  file it was written with (`vectors-<random>.f32`), stale generations are pruned,
  and the loader checks the file size exactly.
- **The `~/notes` default inherited the historical leak shape.** With the vault
  positional swallowed by `--exclude`/`--model`/`--endpoint`, the tool fell back
  to `~/notes` and would have read *and uploaded* the real vault. `--index` was
  hardened first; the query path kept the default, and then promptly reproduced
  the incident during verification — an unsplit zsh word landed as the target and
  the vault silently became `~/notes` (3,035 notes read, nothing uploaded, since
  the target failed to resolve before any embedding). **There is now no default
  anywhere**: the vault must be named as an argument or via `$NOTES_VAULT`, and
  the check runs before the vault is walked.
- **Egress was silent and unrestricted.** The endpoint took any URL, including a
  remote host over plain HTTP, and nothing ever said where note text went. A
  non-loopback endpoint is now refused unless `--allow-remote-endpoint` is passed,
  and every run that embeds prints its destination first.
- **The cache was world-readable** and listed every note title. It is now `0700`/
  `0600`, written via `mkstemp`, and stores only paths, hashes, and vectors.

Also from review: `--rebuild` was added, because a same-named model with different
dimensions could otherwise deadlock (`--index` was incremental, so the one command
the error told you to run could not clear the bad cache).

## New script: `bin/notes-similar`

Python 3, executable, no extension — matches `notes-graph` / `notes-deadlinks`.
Stdlib only (`argparse`, `hashlib`, `json`, `math`, `os`, `sys`), plus
`notes_common` for vault walking and link parsing.

Split across three files to stay under the 400-line limit, along seams that are
real rather than arbitrary:

- `bin/notes-similar` — CLI, note text, ranking, output
- `bin/notes_embed_cache.py` — vectors, the on-disk cache, incremental refresh
- `bin/notes_embed_client.py` — the HTTP client and endpoint validation; note text
  leaves the process only through this module, so the egress rules live with it

`notes_common.printable()` is new and shared: `notes-deadlinks` still carries its
own private copy, which is worth folding in separately.

### Note text

`note_text()` strips YAML frontmatter, prepends the note **name** (titles carry real
meaning in a numbered Zettelkasten), and truncates to `MAX_CHARS` (8,000 ≈ 2,048
tokens). Notes average ~177 words, so truncation is rare and no chunking is needed —
one vector per note.

The content hash is `sha256` of that prepared text, so a frontmatter-only edit
does not trigger a re-embed.

### Cache

`~/.cache/notes-similar/<sha256(vault)[:16]>/` — **never inside the vault**:

- `index.json` — `{model, dims, vectors, notes: [{path, hash}]}`, mode `0600`
- `vectors-<random>.f32` — raw little-endian float32, `len(notes) * dims` values,
  same order, mode `0600`

No note names or text on disk: the cache is derived from private notes, so it
holds only what ranking needs.

Vectors are **L2-normalised at write time**, so a query is a plain dot product.
The vector file is written under a fresh random name, then `index.json` names it —
`index.json` is the commit point, and because it identifies its own vector file,
a crash or a concurrent run can never pair mismatched halves. Older generations
are pruned after a successful write, including a pre-generation `vectors.f32`
left by an earlier version.

The cache is discarded wholesale when the model name changes, when `dims` is out
of range, when the named vector file is missing, or when its size is anything
other than `len(notes) * dims * 4`. Vectors for deleted or edited notes are
dropped on the next save, since only current `(path, hash)` pairs are written back.

### Algorithm

1. `scan_vault()` — one pass per note: read, hash the prepared text, extract its
   `[[wikilinks]]`. Reading is unavoidable (hashing needs the content), so links
   come free in the same pass rather than a second walk.
2. `load_cache()` — map `(path, hash) -> vector`. Any corruption returns empty.
3. `refresh()` — embed only notes missing from that map, in batches of 32.
   In query mode, refuse if more than `--max-refresh` (default 50) are missing.
4. `find_similar()` — `math.sumprod` of the target vector against every other,
   sorted by descending score then name.
5. Unless `--all`, drop notes linked to the target in **either** direction:
   forward links resolved through `notes_common.resolve_link`, backlinks by
   scanning every note's links for one resolving to the target path.

### Degradation

`EmbedUnavailable` wraps every failure mode — connection refused, HTTP error,
malformed or wrong-length response, missing model, unusable index. Query mode
catches it and always emits **valid JSON on stdout with exit 0**:

```json
{"available": false, "error": "…: Connection refused", "similar": []}
```

Exit 0 matters because the lua side parses stdout and ignores the exit code, as
`graph.lua` and `deadlinks.lua` already do.

`--index` is the exception: an explicit request to do work, so a failure prints the
reason and exits **1**.

## Neovim integration: `similar.lua`

Mirrors `deadlinks.lua`, but runs `vim.system` **asynchronously** with a callback
rather than `:wait()`: a query may embed up to `--max-refresh` notes over HTTP,
which can outlast any wait budget worth freezing the editor for (and a kill
mid-write is exactly what the cache pairing fix defends against).
`:ObsidianSimilar` on `<leader>oS`, `:ObsidianSimilarIndex[!]` for a refresh or
rebuild, running `notes-similar <current-file> <vault> --json`.

- Not a markdown buffer in the vault → notify and stop.
- `available: false` → notify the `error` string at WARN, no picker.
- Empty `similar` → "No unlinked similar notes found".
- Rows are `score  name  preview  relpath`, sanitised with `gsub("%c", " ")` for the
  same reason as `deadlinks.lua`: note-derived text must not split one entry across
  several picker lines and desync `path_by_line`.
- `default` action edits the selected note; `ctrl-y` inserts `[[name]]` at the
  cursor in the buffer the picker was opened from.

## Tests

Same harness as `notes-deadlinks_test.py` — `SourceFileLoader`, synthetic vaults
in `tempfile.TemporaryDirectory()`, never `~/notes`. Subprocess cases also set
`HOME` to the temp vault, so the `~/notes` default is physically unable to reach
the real vault from any test, present or future.

No test requires a live embedding server, but the fake must not sit so high that
the protocol goes unexercised — the review's false-green finding. So:

- `bin/notes_embed_client_test.py` runs the **real HTTP path** against a loopback
  `http.server` stub, covering the request shape (including that `input` is a
  list, which servers differ on), response reordering, and every failure branch
- `bin/notes_embed_cache_test.py` covers the cache format, generation pairing,
  permissions, and incremental refresh
- `bin/notes-similar_test.py` covers note text, ranking, link filtering, argument
  handling, and the degraded CLI paths with a `fake_embedder` (seeded by `crc32`,
  not `hash()`, so rankings don't depend on `PYTHONHASHSEED`)

Coverage:

- frontmatter stripping, name prepending, truncation, hash stability
- cache round-trip; invalidation on model change and on truncated `vectors.f32`
- incremental refresh embeds only changed notes; deleted notes are pruned
- ranking order; self is excluded
- linked notes excluded by default in both directions, present under `--all`
- unreachable server → `available: false`, empty `similar`, exit 0, valid JSON
- missing index over `--max-refresh` → refusal, not a multi-minute stall
- target resolution by path and by note name; unknown target is a clean error
