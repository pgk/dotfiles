# bin/ — notes vault tools

`notes-graph` and `notes-deadlinks` default their vault argument to
`~/notes`, the user's real private notes. When developing, testing, or
debugging either script, never let that default apply and never point them
at the real path — use
`../base/nvim/nvim/lua/plugins/obsidian/dev-vault` (a permanent synthetic
fixture) or a `tempfile.TemporaryDirectory()`-built vault instead, as
`notes-graph_test.py` / `notes-deadlinks_test.py` already do. See
`../base/nvim/nvim/lua/plugins/obsidian/CLAUDE.md` for the full rule and why
it exists.
