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
are flags (`--dup-min`, `--dup-title-min`) so they can be re-tuned here.

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

`--per-cluster` (default 3) caps hits shown per cluster; `-n`/`--limit`
(shared with the other modes, default 10) caps how many clusters are shown,
not hits within one — a third meaning for a flag whose meaning already varies
by mode (`--duplicates` uses it to cap only the "possible" band). The query
phrase is embedded fresh on every call and never written to
`~/.cache/ariadne-similar/` — same boundary `--duplicates` already respects
by never writing there either, just enforced for a different reason (nothing
to cache: a typed phrase is rarely repeated verbatim).
