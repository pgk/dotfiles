# bin/ — notes vault tools

`notes-graph`, `notes-deadlinks` and `notes-similar` default their vault
argument to `~/notes`, the user's real private notes. When developing,
testing, or debugging any of these scripts, never let that default apply and
never point them at the real path — use
`../base/nvim/nvim/lua/plugins/obsidian/dev-vault` (a permanent synthetic
fixture) or a `tempfile.TemporaryDirectory()`-built vault instead, as
`notes-graph_test.py` / `notes-deadlinks_test.py` / `notes-similar_test.py`
already do. `notes-similar` additionally sends note text to an embedding
server, so a stray run would leak vault content over HTTP as well as print it —
which is why **`notes-similar` has no `~/notes` default at all**, unlike its two
siblings: every invocation must name the vault, as an argument or via
`$NOTES_VAULT`, and it rejects a non-loopback endpoint unless
`--allow-remote-endpoint` is passed. Keep both guards.

The default was removed after a session accidentally scanned the real vault
again: a `for` loop passed `"--index --exclude drafts/*"` as one unsplit zsh
word, which landed as the *target* and let the vault fall back to `~/notes`.
Nothing was uploaded (the target failed to resolve first) but all 3,035 notes
were read. The check now runs before the vault is walked, so the same typo costs
nothing. See
`../base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` for the full rule and why
it exists.
