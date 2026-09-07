# bin/ — notes vault tools

`ariadne-graph` (including its `--since` and `--neglected` reports),
`ariadne-deadlinks` and `ariadne-similar` all read a whole notes vault. **None of
them has a `~/notes` default**: every invocation must name the vault, as an
argument or via `$NOTES_VAULT`, and the check runs before the vault is walked so
a bad invocation costs nothing. The guard is
`ariadne_common.require_vault()` — keep it, and don't reintroduce a default in any
sibling tool.

When developing, testing, or debugging these scripts, never point them at the
real path — use `../base/nvim/nvim/lua/plugins/ariadne/dev-vault` (a permanent
synthetic fixture) or a `tempfile.TemporaryDirectory()`-built vault instead, as
`ariadne-graph_test.py` / `ariadne-deadlinks_test.py` / `ariadne-similar_test.py`
already do. `ariadne-similar` additionally sends note text to an embedding server,
so a stray run would leak vault content over HTTP as well as print it; it also
rejects a non-loopback endpoint unless `--allow-remote-endpoint` is passed. Keep
that guard too.

The defaults were removed after a session accidentally scanned the real vault
again: a `for` loop passed `"--index --exclude drafts/*"` as one unsplit zsh
word, which landed as the *target* and let the vault fall back to `~/notes`.
Nothing was uploaded (the target failed to resolve first) but all 3,035 notes
were read. `ariadne-similar` lost its default then; `ariadne-graph` and
`ariadne-deadlinks` kept theirs until the clustering work, which is when the same
hazard was noticed still sitting in both. See
`../base/nvim/nvim/lua/plugins/ariadne/CLAUDE.md` for the full rule and why
it exists.

`ariadne-embed-setup` is the exception: it never touches the vault at all. It only
ensures `ariadne-similar`'s Ollama embedding model is pulled, shelling out to
`ollama list`/`ollama pull` — no `ariadne_common` import, no vault argument, by
design.

## The backlinks block is not authored text

`:AriadneBacklinks` writes a `<!-- ariadne:backlinks -->` block into a note
listing what links to it. `ariadne_common.strip_backlinks_block` drops it, and
`extract_links` calls that itself so no links caller here can forget to — read
it before adding a tool that reads note text. `ariadne_note_text.note_body` and
`ariadne_splittable.note_stats` strip it separately, because they read the note
as prose as well as for links. The full reasoning, and what breaks without it,
is in `../base/nvim/nvim/lua/plugins/ariadne/CLAUDE.md`.

## What gets embedded

`ariadne_note_text.py` owns this end — `note_chunks()`, `content_hash()`,
`preview_of()` and their constants. It was split out of `ariadne-similar` when
that script crossed the 400-line limit, and it knows nothing about vectors, the
cache, or the CLI.

`note_chunks()` embeds the note *name* followed by the body, with every `[[wikilink]]` flattened to the words a reader sees
(`ariadne_common.wikilink_display`). Both matter: body-only embeddings made
short notes with descriptive titles hard to retrieve, and an unflattened link
is punctuation and a slug where the reader sees two words of meaning.
Changing either changes every note's content hash, forcing a full re-index —
the `--max-refresh` guard turns that into an honest "run --index" message
rather than a silent multi-minute upload, which is the behaviour to keep.
`--max-refresh` counts **notes**, not chunks: counting chunks would inflate the
same vault without changing what the number is supposed to mean.

A note over `CHUNK_THRESHOLD` (1500 characters) is split at its own `##`
headings, and any section still over `CHUNK_WINDOW` is windowed with an
overlap. A note at or under the threshold yields one chunk byte-identical to
`note_text()`, so its vector cannot move — which is why chunking is
conditional. Everything past `MAX_CHARS` used to be discarded outright, and on
the largest notes that was most of the body.

Past `MAX_SECTIONS` (32) the sections are **packed** together up to the window
instead of each becoming a vector, and `MAX_CHUNKS` (40) is a hard ceiling on
the vectors one note can produce — packing helps only a note shredded into tiny
sections, so a genuinely huge note still needs a cap. A note that is a list of short headings is
otherwise shredded — 163 chunks for one real note in `obsidianmd/obsidian-help`
— and since a query scores every chunk of the *target*, that one note would
take ~4.7 s to query. The cap costs almost nothing measurable (MRR .225 →
.223 on the wikilink corpus, worst case 59 chunks → 27); packing *every* note
costs .225 → .216, which is why it is a cap and not the rule.

The cache entry for a note is its **centroid first, then its chunks**
(`ariadne_embed_cache.note_entry`, read back through `note_vector()` /
`chunk_vectors()`). The centroid is stored rather than derived because every
comparison uses it and recomputing them all costs ~0.5 s per invocation — more
than a whole query.

## How two notes are scored

Asymmetrically, and this is the load-bearing decision: **chunks on the query
side, one centroid on the document side** (`best_chunk_match`). The obvious
alternative is ColBERT's MaxSim — the max over every chunk *pair* — and it was
measured worse. A max over k samples rises with k, so a note that splits into
59 chunks outscores a one-chunk note against everything: on a 326-note public
vault the background similarity was 0.295 for one-chunk notes against 0.379 for
notes of four chunks or more, and MRR fell from 0.206 (unchunked baseline) to
0.181. Scoring documents by their centroid removes that bias, and the query
side stays chunked because it costs nothing — the target's chunk count is
constant across every candidate, so it cannot bias a ranking, and it is worth
MRR 0.208 → 0.225.

The corpus matters to that conclusion. Two synthetic corpora with a planted
concept-sharing ground truth prefer MaxSim by a wide margin, but their related
notes *share literal passages*, which is exactly what a max over chunk pairs
finds; the wikilink corpus is the closer proxy for what `--similar` actually
answers. Under centroid scoring, chunking beats the unchunked baseline on all
three (MRR +9%, +3%, +4%). What it does **not** buy is the dilution win: a
multi-idea note scored by its centroid is still averaged, and the synthetic
"several ideas in sections" case is neutral-to-slightly-worse. Fixing that
needs a doc-side max, which costs more than it gains. See
`doc/plans/PLAN-0008-chunked-embedding-index.md` for the full tables.

Query cost stays flat in the size of the cache — only the *target's* chunk
count multiplies the work, which is what `MAX_CHUNKS` bounds. 29 ms for a
one-chunk target against 3,000 notes, 337 ms for a 12-chunk one, 1.2 s at the
ceiling, which is why `numpy` is still not needed.

`MAX_CHUNKS` also keeps the write and read sides of the cache in agreement.
`load_cache` drops the **whole** cache on an entry over `MAX_VECTORS`, so
writing one would mean re-embedding and re-uploading the entire vault on every
run, for ever, with no diagnostic — `save_cache` refuses rather than write it.

## `--exclude`

`ariadne_common.matched_excludes()` tests a pattern against a note's relative path
**and every directory above it**, case-insensitively. `--exclude journal` therefore
excludes the whole subtree, and `Journal` matches it too — the vault normally sits on
a case-insensitive filesystem, where those name the same directory. Excluded
directories are pruned from the walk, not filtered afterwards, so their contents are
never read. A pattern matching nothing warns on stderr.

Both properties matter beyond ergonomics: `--exclude` is the only mechanism keeping a
subtree out of `ariadne-similar`'s HTTP upload, and it previously matched only whole
relative paths, case-sensitively — so `--exclude journal` and `--exclude Journal/*`
each silently excluded nothing.

## `--duplicates`

`ariadne-similar --duplicates` reuses the embedding cache to answer a different
question from the default query, and needs two signals to answer it:
`ariadne_duplicates.EMBED_MIN` (0.80 cosine) makes a pair a candidate,
`TITLE_MIN` (0.85 `difflib` ratio over the names) makes it a duplicate rather
than a question. Measured elsewhere on a 37-note corpus: the one genuine
duplicate scored 0.842 cosine / 1.000 title, every other pair over 0.80 cosine
scored at most 0.430 title. **Don't drop the title signal** — cosine alone
cannot separate "the same note twice" from "a neighbouring idea", which is the
job the default query already does.

Both numbers are borrowed calibration, not a measurement of this vault; they
are flags (`--dup-min`, `--dup-title-min`) so they can be re-tuned here. They
also predate chunking, and were taken against whole-note vectors truncated at
`MAX_CHARS`. Notes under `CHUNK_THRESHOLD` still have exactly that vector, so
only long-note pairs moved — but the cosine bar has not been re-checked against
centroids.

The scan is every-pair with no index structure: 48s for 4.6M pairs at 3040 notes
and 768 dims, measured against a real warm cache. A warm cache does not help —
it saves the embedding round trip, not the comparison.

That 48s holds **at the default `--dup-min`**, where almost nothing clears the
cosine gate so the title is almost never computed. Lowering it pays
`SequenceMatcher.ratio()` on far more pairs, at 13-32 us against the dot
product's 9.4 us — `--dup-min 0` on a vault this size is minutes, not seconds.
If that becomes a real invocation, the fix is `real_quick_ratio()` /
`quick_ratio()` as a prefilter: both are documented upper bounds on `ratio()`,
so a pair already destined for eviction settles without the exact ratio. Note
`ratio()` is **not symmetric** — pin `seq2` to the inner-loop name or the
verdict changes. That is why it is its own mode. If it ever needs to be faster,
the honest fix is a blocking key on the title, not an approximate vector index —
the title is the cheap signal and it is already required.

## What the embeddings are for

`ariadne-similar` answers "find the note I half-remember but cannot name" — and
`--duplicates` answers "did I write this twice". Both are retrieval. The project
this was salvaged from spent years using embeddings to *assemble context for
generation* instead and retired that as never having been the point. If a
third mode is ever added here, check which of the two jobs it is doing.

`--search` (a third mode, added later) is the first job, not a new one — "find
the note I half-remember" with a typed phrase standing in for the note the
default query anchors on instead. It answers a harder version of the same
question: with no target note, there is no cluster of its own for a hit to
cross or stay within, so `--search` groups by cluster rather than ranking
crossing-vs-within, to keep one tight cluster's hits from burying a good match
elsewhere in the vault. See `ariadne_search.py`.

## `--search`

The phrase goes to the model under embeddinggemma's retrieval-query prefix
(`ariadne_search.QUERY_PREFIX`), documents do not. The model is trained
asymmetrically, and the query is the only side that can be changed for free:
it is embedded fresh per call, so nothing is re-indexed. Measured on a 495-note
public corpus (title-as-query retrieval): +1.5% MRR against today's document
format, 24 queries better and 9 worse. **Document**-side prefixing looked
better still on that fixture, but the fixture queries *are* the titles, which
is exactly what a `title: X | text: Y` document format rewards — and it would
force a re-index of the whole vault to serve the mode that isn't the primary
one. Not adopted on that evidence.

### `--search --from NOTE`

`--from` names the note a phrase was lifted out of, which is what turns a typed
search into a passage query: that note is excluded from its own results, and it
supplies the cluster and the existing links, so the ranking goes back to
crossing-vs-within and the payload is the `similar` shape rather than `groups`.
`--all` and `--no-bridge` are refused with a bare `--search` and accepted with
`--from`, for the same reason — with `--from` there is a target note for them to
mean something about. Positionally nothing changes: `--from` is a flag argument,
so `--search` is still vault-only.

Three things differ from a typed phrase, all measured on four public corpora
over two seeds, 522 source notes, with the source note as the unit:

- **No query prefix.** `QUERY_PREFIX` is worth +1.5% MRR on *title-shaped*
  queries and nothing on lifted passages — pooled −0.6% / −0.8% over 522 source
  notes in four public corpora, two seeds, both intervals spanning zero. Note
  the corpora *disagree* rather than agreeing on zero (a 326-note wiki loses
  ~1.5% under the prefix, a 23-note vault gains ~9%), so this is a weak call
  taken on the grounds that a prefix whose only measured benefit is for a
  different query shape should not be applied on faith. Document-side prefixing
  is consistently worse and is out.
- **The passage is normalized exactly as a document is** — `note_body()`:
  frontmatter dropped, `[[wikilinks]]` flattened. The index is built that way,
  so a raw selection would spend the model's budget on brackets and slugs the
  documents do not have, and the daily note this feature is for is
  wikilink-dense. Same argument as the name prefix above: match the shape the
  index was built in. `passage_chunks(body, name) == note_chunks(name, body)`
  is asserted, which is the cheapest way to keep the two ends from drifting.
- **The passage is chunked.** `passage_chunks()` windows a long selection the
  way `note_chunks()` windows a note, reusing the same `_sections` / `_windows`
  / `_packed`, so a long selection is not silently truncated at the model's
  context. `MAX_QUERY_CHUNKS` (8) is far tighter than `MAX_CHUNKS` (40) on
  purpose: the note ceiling bounds what is stored, this one bounds one
  interactive query, since every query chunk is scored against every note.

  **Packing is gated on `MAX_QUERY_CHUNKS`, not `MAX_SECTIONS`** — do not
  "align" it with `note_chunks`. There the gate (32) is *below* the cap (40), so
  no section is ever lost; here the cap is 8, so gating at 32 meant a selection
  of 9 to 32 short sections got no packing and had everything past the eighth
  silently dropped — 61% of a 20-section selection, measured. Found by review.
- **The origin note's name is prefixed — but only when it carries words.** This
  is the one conditional in the file, and it is conditional because both halves
  were measured. A real name on every chunk, matching how documents are stored
  (`name\n\nbody`), is worth **+2.7% and +1.8% MRR** across two seeds, positive
  on all four public corpora. An *uninformative* name is not merely inert:
  replacing every corpus title with a date-shaped string, changing nothing else,
  costs **−2.2% and −2.0% pooled** over the same two seeds, and **−3.8% / −3.6%**
  on the largest corpus, every one of those intervals excluding zero. That is exactly the
  daily note the feature exists for — `2026-09-05` says nothing about the
  passage, and date strings are highly similar to *each other*, the same effect
  that already defeats `--duplicates`' title gate. `informative_name()` is the
  gate: a run of two or more letters in any script. It rejects `2026-09-05`,
  `20260905` and a bare folgezettel id like `1a2b`, and accepts `1a2b Some
  Title`, which is the shape `branch.lua` actually creates.

`--from` resolves **strictly** when it names a path: `resolve_target(...,
path_only=True)`. The bare-name fallback is still there for `--from some-note`,
but a *path* must match a note that was actually scanned, matched against either
the path it was scanned under or its realpath. Both halves are load-bearing:

- Without the strict match, `--from drafts/scratch.md --exclude 'drafts/*'`
  silently resolved to `archive/scratch.md` — a different note, which then
  labelled the results, got excluded from them, and became ctrl-y's wikilink
  target. Found by review, reproduced, now pinned.
- Without the realpath pass, the strict match would break the editor outright.
  nvim reports a buffer's name with symlinks resolved while the vault stays as
  configured, so in a symlinked vault (`~/notes -> ~/Dropbox/notes`) the
  scanned-path comparison matches *nothing*. The realpath scan runs only when
  the cheap comparison misses.

The whole-note query path still uses the lenient form, so `ariadne-similar
subdir/note.md VAULT` keeps working from a shell.

The ranking itself moved to `ariadne_ranking.py` when `--from` pushed
`ariadne-similar` past 400 lines — same reason `ariadne_note_text.py` came out
of it earlier. `rank_against(query_chunks, origin, ...)` is the general form and
`find_similar(target, ...)` is the whole-note case that passes the target's own
stored vectors; `ariadne-similar` re-exports both under their old names so the
suites reaching them through it needed no change.

`--per-cluster` (default 3) caps hits shown per cluster; `-n`/`--limit`
(shared with the other modes, default 10) caps how many clusters are shown,
not hits within one — a third meaning for a flag whose meaning already varies
by mode (`--duplicates` uses it to cap only the "possible" band). The query
phrase is embedded fresh on every call and never written to
`~/.cache/ariadne-similar/` — same boundary `--duplicates` already respects
by never writing there either, just enforced for a different reason (nothing
to cache: a typed phrase is rarely repeated verbatim).
