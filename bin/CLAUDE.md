# bin/ — notes vault tools

`notes-graph` (including its `--since` and `--neglected` reports),
`notes-deadlinks` and `notes-similar` all read a whole notes vault. **None of
them has a `~/notes` default**: every invocation must name the vault, as an
argument or via `$NOTES_VAULT`, and the check runs before the vault is walked so
a bad invocation costs nothing. The guard is
`notes_common.require_vault()` — keep it, and don't reintroduce a default in any
sibling tool.

When developing, testing, or debugging these scripts, never point them at the
real path — use `../base/nvim/nvim/lua/plugins/obsidian/dev-vault` (a permanent
synthetic fixture) or a `tempfile.TemporaryDirectory()`-built vault instead, as
`notes-graph_test.py` / `notes-deadlinks_test.py` / `notes-similar_test.py`
already do. `notes-similar` additionally sends note text to an embedding server,
so a stray run would leak vault content over HTTP as well as print it; it also
rejects a non-loopback endpoint unless `--allow-remote-endpoint` is passed. Keep
that guard too.

The defaults were removed after a session accidentally scanned the real vault
again: a `for` loop passed `"--index --exclude drafts/*"` as one unsplit zsh
word, which landed as the *target* and let the vault fall back to `~/notes`.
Nothing was uploaded (the target failed to resolve first) but all 3,035 notes
were read. `notes-similar` lost its default then; `notes-graph` and
`notes-deadlinks` kept theirs until the clustering work, which is when the same
hazard was noticed still sitting in both. See
`../base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` for the full rule and why
it exists.

## `--exclude`

`notes_common.matched_excludes()` tests a pattern against a note's relative path
**and every directory above it**, case-insensitively. `--exclude journal` therefore
excludes the whole subtree, and `Journal` matches it too — the vault normally sits on
a case-insensitive filesystem, where those name the same directory. Excluded
directories are pruned from the walk, not filtered afterwards, so their contents are
never read. A pattern matching nothing warns on stderr.

Both properties matter beyond ergonomics: `--exclude` is the only mechanism keeping a
subtree out of `notes-similar`'s HTTP upload, and it previously matched only whole
relative paths, case-sensitively — so `--exclude journal` and `--exclude Journal/*`
each silently excluded nothing.
