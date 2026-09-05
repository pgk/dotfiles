# Chunked embedding index, and a query-side prefix for `--search`

## Context

`ariadne-similar` embeds one vector per note: `note_text()` builds
`"{name}\n\n{body}"` and slices it at `MAX_CHARS = 8000`. Two defects follow.

**Truncation.** Everything past 8000 characters never reaches the model. On a
vault of a few thousand notes this discards hundreds of thousands of
characters, and the largest notes lose most of their body. A second cut sits
underneath: embeddinggemma's context is 2048 tokens, and its Modelfile is
`TEMPLATE {{ .Prompt }}` — a passthrough that adds no prefix — so long input
is cut again inside the model.

**Dilution.** A note covering several ideas averages into one vector, so no
single idea is well represented. `ariadne-graph` already flags this population
`[SPLIT]`: the tool can say a note is too big to be one idea, then embeds it
as one anyway.

### Read before benchmarking anything here

An earlier session measured all of this **against the real vault**, which
`bin/CLAUDE.md` forbids — eight scratch scripts hardcoding the user's note
vault path, and ~48,000 embedding requests carrying note text. Loopback only,
no cache written, but the rule is unconditional and those
numbers are **unusable**. No decision here rests on them. One artefact of that
run survives below and is labelled where it appears: the `--search` prefix
table, marked inadmissible and blocking its own change until redone. See
auto-memory `never-benchmark-against-the-real-vault`.

The replacement is `scratchpad/synth/build.py`: real prose from seven public
vaults, composed into notes with a planted concept-sharing ground truth. Two
vaults from identical content, differing only in size distribution. Not
committed — the benchmark stays a scratch tool.

| case | construction | decides |
| --- | --- | --- |
| A | one concept, <1500 ch | chunking must be **neutral**; ~70% of the target vault |
| B/C | one concept, medium/long | neutral |
| D | 3–5 concepts in sections | **dilution** — chunking should win |
| E | concepts placed past 8000 ch | **truncation** — baseline cannot retrieve at all |
| F | hub note, links not prose | must not become a false-positive magnet |

## Measurements

508 notes per vault; 1,666 and 2,228 ground-truth pairs.

```
vault-short (p50 446)      all              case A         case D         E-trunc
baseline 1-vec        MRR .454 r@10 .801 | .471 .862    | .157 .539    | .009 .000
chunk 700             MRR .492 r@10 .921 | .450 .901    | .378 .904    | .619 1.000
chunk 1500            MRR .492 r@10 .918 | .443 .901    | .400 .893    | .635 .986

vault-medium (p50 870)
baseline 1-vec        MRR .362 r@10 .670 | .365 .753    | .170 .517    | .008 .000
chunk 700             MRR .415 r@10 .846 | .365 .804    | .297 .757    | .436 .946
chunk 1500            MRR .415 r@10 .852 | .341 .804    | .312 .786    | .457 .959
```

Truncation is total, not partial — baseline recall@10 is **0.000**, chunking
**1.000**. That holds however "related" is defined, because the bytes are
absent from the index. Case A's small mixed result (MRR down, r@10 up) is the
neutrality check passing; a fixture improving every case uniformly would be
rigged.

**Retracted claims of this work — do not resurrect without new evidence:**

- *Chunk size matters.* 700 and 1500 tie on both vaults. An earlier "700 is
  best" does not replicate.
- *Mean-centering helps.* .454→.455 and .362→.360. An earlier +3–4% does not
  replicate; **do not adopt it**.
- *Note-size distribution explains the wikilink contradiction below.* Chunking
  won on both distributions, and won more on the medium one.

**Fixture confound.** Ground truth is *content provenance*: related notes hold
passages from one source document, so they share literal text, which
max-over-chunks finds easily. Against a real public vault's **wikilinks**
(`younggulsong/my-wiki`, 326 notes, 2,518 pairs), uniform chunking was
**worse** — MRR .206 → .166. Wikilinks are the closer proxy for what
`--similar` does, so that result stands — and it turned out to be the thread
worth pulling. See "Scoring, resolved".

## Design

### Conditional chunking, not uniform

Chunk only notes above a size threshold. Case A is the sole slice where
chunking costs precision and the bulk of the target vault; the proven wins
live entirely in long notes. A note below the threshold yields one chunk equal
to today's `note_text()` output, so its vector is byte-identical and cannot
regress.

### `note_text()` → `note_chunks()`

Split the body on `^#{2,6} ` boundaries, window any part still oversized,
prefix every chunk with the note name. Chunk size measured as irrelevant, so
take the unit from structure rather than tuning it. Shipped in its own module,
`ariadne_note_text.py` — `ariadne-similar` crossed the 400-line limit.

One thing structure alone does not bound is the chunk *count*. A note that is a
list of short headings becomes one vector per heading: 163 of them for a real
note in `obsidianmd/obsidian-help`, and since a query scores every chunk of the
target, that note alone would be a ~4.7 s query. Past `MAX_SECTIONS` (32) the
sections are packed together up to the window. Measured on the wikilink corpus:

```
split at every heading   1503 vec, max 59   MRR .225 r@10 .467
packed to the window      650 vec, max 23   MRR .216 r@10 .446
plain, packed over 32    1372 vec, max 27   MRR .223 r@10 .462   <- shipped
```

Packing everything is leaner but costs real accuracy; the cap costs .002 and
takes the worst case from 4.7 s to 0.8 s. On `vault-medium` packing everything
was a slight *gain* (.378 → .380), so the cost is specific to notes with many
substantial short sections — exactly the ones the cap leaves alone.

Carrying the section heading onto continuation windows measured as **no
effect** where it could be isolated — identical to three decimals at 1500. Add
it only if a later measurement earns it.

### Cache format

`(path, hash) -> vector` becomes `(path, hash) -> [centroid, *chunks]`;
`index.json` entries gain a `vectors` count and the vector file stores
`sum(counts)` vectors in order. `load_cache()` already returns `{}` on schema
inconsistency, so old caches self-invalidate rather than mispair — an entry
with no count cannot even be located in the vector file, which is the failure
mode that had to be impossible. Full re-index, ~3.5 min.

`content_hash()` now covers the whole chunk list rather than `note_text()`:
that stopped at `MAX_CHARS`, so two notes agreeing for 8000 characters and
diverging after would have shared a hash.

### Scoring: ~~max over chunks~~ query chunks against document centroids

**Superseded before it shipped — see "Scoring, resolved" below.** The original
design was ColBERT's MaxSim at chunk rather than token granularity, on both
sides. Measurement showed the *document* side of that is what causes the
wikilink regression this plan could not explain.

### `--duplicates` uses note centroids

The mean of a note's chunks, renormalised. "Did I write this twice" is a
note-level question, and one vector per note keeps the documented 48s scan
from becoming ~183s. For single-chunk notes the centroid *is* the vector.

As shipped this is no longer special to `--duplicates`: the centroid is every
mode's document-side vector, and it is stored as the first vector of each cache
entry rather than recomputed, which would cost ~0.5 s per invocation.

### `--max-refresh` keeps counting notes

Counting chunks would inflate the same vault 2.2–4.6× (measured across the
three corpora) and silently change what the number means. `bin/CLAUDE.md` calls this guard's honest "run `--index`"
message "the behaviour to keep".

### Query-side prefix for `--search` — resolved below, adopted

**These numbers came from the disallowed real-vault runs and must be
re-measured on a public corpus before anything ships on them.** Recorded
because the shape of the result is worth re-testing, not because it is
established. Title-as-query retrieval, 700 notes:

```
query fmt              doc fmt                 r@1     MRR
raw title              name\n\nbody (TODAY)    0.791   0.851
task: …| query: X      name\n\nbody (TODAY)    0.837   0.881   <- candidate
raw title              title: X | text: Y      0.844   0.895
task: …| query: X      title: X | text: Y      0.863   0.905
```

The candidate change is the query prefix alone, in `run_search()`: it altered
no document text, so it would need no re-index, and the query is embedded
fresh per call and never cached. The document format looked worse for
note-to-note similarity, which is the primary mode — but that comparison has
the same provenance problem. Note the model card recommends both prefixes
while the measurement favoured one; that is the thing worth re-testing.

## Rejected — do not re-derive

- **numpy.** The query path is 69 ms for 5,200 vectors in pure stdlib.
  `python3` here is Homebrew 3.14 under PEP 668, `make pip` cannot install
  into it, and nvim invokes these tools through a bare `#!/usr/bin/env
  python3` shebang, so a hard import breaks `:AriadneSimilar` with
  `ModuleNotFoundError`. Centroid `--duplicates` removes the only case where
  numpy paid.
- **CSLS.** Needs an all-pairs density pass measured at 100–135 s — impossible
  per query.
- **Late chunking (Jina).** Better in principle: embed the document, then pool
  per chunk. Needs token-level embeddings before pooling, which Ollama's
  `/v1/embeddings` does not expose, and 8192-token models where embeddinggemma
  has 2048. Unreachable here, not unwanted.
- **Raising `MAX_CHARS`.** Only moves the cut; the model truncates at 2048
  tokens regardless.

## Tests

`ariadne-similar_test.py`, `ariadne_embed_cache_test.py`,
`ariadne_search_test.py` and `ariadne_duplicates_test.py` assume one vector
per note. Add: a sub-threshold note yields one chunk byte-identical to
`note_text()`; an oversized section windows; an old-format cache invalidates
rather than mispairs; a single-chunk note's centroid equals its vector.

```sh
cd bin && for f in *_test.py; do printf "%-34s " "$f"; python3 "$f" 2>&1 | tail -1; done
```

## Both TODOs, resolved

### `--search` prefix, re-measured and admissible

495 public notes — the six small vaults in `scratchpad/corpora` plus
`obsidianmd/obsidian-help`'s `en/` tree, deduplicated by title. Same
title-as-query proxy as the inadmissible table, on a corpus the rules allow.

```
query fmt              doc fmt                 r@1     MRR
raw title              name\n\nbody (TODAY)    0.921   0.956   <- today
task: …| query: X      name\n\nbody (TODAY)    0.949   0.971   <- shipped
raw title              title: X | text: Y      0.960   0.977
task: …| query: X      title: X | text: Y      0.970   0.983
```

The query prefix alone is +1.5% MRR against today's document format, 24 queries
better and 9 worse; +3.0% against body-only documents, where the title's
lexical assist is absent. The direction replicates the retracted table.
**Adopted** (`ariadne_search.QUERY_PREFIX`), and it needs no re-index.

Document-side prefixing is *not* adopted. It looks better on this fixture, but
the fixture's queries **are** the titles, which is precisely what a `title: X |
text: Y` document format rewards — and it would force a full re-index to serve
the mode that is not the primary one.

### Conditional chunking: the hypothesis was wrong, and the reason is worth keeping

Conditional chunking at 1500 characters, all three corpora, scored with
max-over-chunk-pairs as originally designed:

```
                        all           case A/tgt<1500   case D     E-trunc
vault-short  baseline   .454 r@10 .801   .471 .862    .157 .539   .009  .000
             uniform    .492      .919   .443 .901    .398 .893   .681 1.000
             cond-1500  .492      .919   .443 .901    .398 .893   .681 1.000
             trunc-only .473      .855   .459 .883    .147 .506   .675  .958
vault-medium baseline   .362      .670   .365 .753    .170 .517   .008  .000
             cond-1500  .414      .847   .343 .798    .310 .775   .490  .959
             trunc-only .375      .709   .358 .763    .163 .493   .511  .878
my-wiki      baseline   .206      .421   .201 .399
             uniform    .166      .363   .161 .349
             cond-1500  .181      .396   .176 .374
             trunc-only .194      .410   .187 .387
```

Conditional chunking narrows the wikilink regression (−19% → −12%) but does not
remove it, and the truncation-only fallback still costs −6%. **The plan's
hypothesis is falsified, and so is its fallback.**

### Scoring, resolved

The regression is not chunking. It is `max` on the *document* side. A max over
k samples rises with k, so a note that splits into 59 chunks outscores a
one-chunk note against everything. Measured directly — each note's mean score
against every query — the background level is:

```
                  1-chunk notes   >=4-chunk notes
my-wiki               0.295            0.379   (n=145 / 136, max 59 chunks)
vault-short           0.249            0.338
vault-medium          0.268            0.359
```

One embedding pass, then every combination of query-side and document-side
aggregation:

```
                               all         case A/tgt<1500  case D     E-trunc
my-wiki      baseline     .206 r@10 .421   .201 .399
  cond-1500  q=max d=max  .181      .396   .176 .374
  cond-1500  q=max d=cent .225      .467   .217 .434   <- shipped
  cond-1500  q=cent d=cent .208     .432   .196 .392
vault-short  baseline     .454      .801   .471 .862   .157 .539   .009 .000
  cond-1500  q=max d=max  .492      .919   .443 .901   .398 .893   .681 1.000
  cond-1500  q=max d=cent .468      .858   .482 .913   .152 .455   .175  .479
vault-medium baseline     .362      .670   .365 .753   .170 .517   .008  .000
  cond-1500  q=max d=max  .414      .847   .343 .798   .310 .775   .490  .959
  cond-1500  q=max d=cent .378      .750   .404 .837   .132 .424   .150  .446
```

**Shipped: `q=max d=cent`** — the query note matches on any one of its chunks,
every candidate is scored by its centroid. It beats the unchunked baseline on
**all three** corpora (+9%, +3%, +4% MRR), turns case A from the plan's
"neutrality check" into an actual gain, and recovers truncated content from
r@10 0.000 to 0.45–0.48. Query cost is flat in the size of the cache: 29 ms for
a one-chunk target over 3,000 notes, 337 ms for a 12-chunk one, so `numpy`
stays rejected. The query side keeps its chunks because the target's chunk
count is constant across every candidate and so cannot bias a ranking — worth
MRR 0.208 → 0.225 on the wikilink corpus.

`q=max d=max` scores far better on both synthetic corpora — and that is the
provenance confound this plan already flagged, now doing exactly what was
predicted of it. Those corpora's related notes hold passages from one source
document, so they share literal text, which a max over chunk *pairs* finds
trivially. The wikilink corpus is the closer proxy, and there `q=max d=max` is
the worst configuration measured.

### What this does not deliver

**Dilution.** A multi-idea note scored by its centroid is still averaged: case
D goes .157 → .152 and .170 → .132. The fix for dilution is a document-side
max, and a document-side max costs more on the honest corpus than it gains.
`ariadne-graph`'s `[SPLIT]` signal remains the answer to a note holding several
ideas — split it, and the index follows.

Reviving a document-side max needs per-note score normalisation to cancel the
chunk-count bias, which is an all-pairs density pass — the same 100–135 s that
got CSLS rejected above. Not reachable per query.

## Review, and the final numbers

`code-reviewer` and `security-reviewer` in parallel on the diff. Both landed on
the same two, and both were real:

- **`save_cache` could write an entry `load_cache` always rejects.** One note
  over ~5 MB produces more than `MAX_VECTORS` chunks; `load_cache` then drops
  the *whole* cache, so every run would re-embed and re-upload the entire vault,
  for ever, with no diagnostic. Fixed at the source (`MAX_CHUNKS = 40`) and
  refused at the write side, so the two bounds cannot disagree.
- **`refresh()`'s whole-note commit had no test.** A mutation committing
  half-notes passed all 17 suites. A half-note is stored under the note's real
  content hash, so it is never re-embedded and every later score against it uses
  a centroid of half the note.

Six tests were false greens — each passed while the behaviour it named was
broken, proven by mutation, and each is now pinned the same way:

| test | why it could not fail |
| --- | --- |
| single `#` is not a boundary | the fixture was under the threshold, so it never reached the splitter |
| windowing covers the section | periodic filler matched a dropped tail anywhere |
| at-threshold note is not split | could not tell "one chunk" from "split into one piece" |
| preview comes from the first chunk | single-chunk fixture: `chunks[0] is chunks[-1]` |
| vector path traversal is rejected | the size check rejected it, not the basename guard |
| `--exclude` prunes the walk | asserted on the file list, identical without pruning |

Also from review: fence-aware section splitting (a `## ` inside a code block was
splitting notes mid-fence — the shared `FENCE_RE` now lives in `ariadne_common`
so it cannot drift from `ariadne_splittable`), no degenerate tail windows (a
200-character mostly-overlap tail carried as much of the centroid as a full
window), and `announce()` now states chunks and kilobytes — the note count had
stopped describing the upload once `--max-refresh` no longer bounded it.

Those changed the chunker, so the headline numbers were re-taken against the
code as shipped (`bench_shipped.py`, importing `note_chunks` directly so there
is no second implementation to drift):

```
                        all              case A       case D      E-trunc
my-wiki      baseline  MRR .206 r@10 .421
             shipped       .223      .462
vault-short  baseline      .454      .801   .471 .862  .157 .539  .009 .000
             shipped       .468      .856   .481 .910  .152 .461  .174 .465
vault-medium baseline      .362      .670   .365 .753  .170 .517  .008 .000
             shipped       .378      .750   .401 .837  .133 .426  .158 .486
```

Better than the unchunked baseline on all three corpora, case A improved rather
than merely neutral, truncated content recovered from r@10 0.000 to 0.47–0.49 —
and case D still says what it said before: dilution is not fixed.

## Status

Shipped. Truncation is fixed, the query prefix is in, dilution is not solved and
is documented as not solved. The benchmark scripts stay scratch —
`bench_conditional.py`, `bench_aggregation.py`, `bench_packing.py`,
`bench_shipped.py`, `qprefix_public.py`, `query_speed.py`, `centroid_speed.py` —
and every one that touches a vault refuses any path outside
`scratchpad/corpora` or `scratchpad/synth`.
