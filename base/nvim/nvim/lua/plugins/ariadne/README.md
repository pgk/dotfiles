# ariadne/ — the Zettelkasten workflow for Neovim

A wikilink-based notes workflow layered on
[obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim), for the
private vault at `~/notes`. Most of the interesting logic lives in
stdlib-only Python CLI tools in dotfiles' `bin/` (`ariadne-graph`,
`ariadne-deadlinks`, `ariadne-similar`, `ariadne-embed-setup`); this plugin is a
thin Lua layer that wires their `--json` output into fzf-lua pickers.

- **Full user-facing docs, keybindings, and commands:**
  [`../../../ariadne.md`](../../../ariadne.md)
- **Development rules for this directory** — never touch the real vault,
  safety history, testing: [`CLAUDE.md`](CLAUDE.md)
- **In-editor help:** `:AriadneHelp` / `<leader>oh` opens the doc above.

## Files

| File | Purpose |
|---|---|
| `init.lua` | Plugin spec — loads obsidian.nvim, wires up every module below, global keymaps |
| `utils.lua` | Shared helpers: vault path, safe `edit`/`write`, `sanitize`, `sample`, `run_ariadne_tool` |
| `commands.lua` | Misc commands: random note, insert link, rename, extract-to-note, help |
| `daily.lua` | Daily note template — on-this-day, neglected, and review sections |
| `anniversary.lua` | Date logic behind the "on this day" section |
| `panel.lua` | Links panel sidebar (forward links + backlinks) |
| `transclusion.lua` | Inline `![[note]]` rendering |
| `format.lua` | Custom `formatexpr` so `gw`/`gq` cannot break a `[[wiki link]]` across lines |
| `graph.lua` | Orphan/sparse/splittable notes and hubless clusters (`:AriadneGraphHealth`) |
| `deadlinks.lua` | Dead `[[links]]` with fuzzy-matched candidates (`:AriadneDeadLinks`) |
| `similar.lua` | Semantically similar but unlinked notes, via a local embedding server (`:AriadneSimilar`) |
| `duplicates.lua` | Near-duplicate notes, on embedding *and* title similarity (`:AriadneDuplicates`) |
| `delete.lua` | Move the current note to `.trash/`, gating on what links to it (`:AriadneDelete`) |
| `wikilinks.lua` | Parsing and rewriting `[[links]]` — resolution keys, display text, unwrapping |
| `activity.lua` | Recently touched notes, grouped by link community (`:AriadneActive`) |

`dev-vault/` is a permanent synthetic fixture — never the real vault — used
by both the Lua specs here and the Python tests in `bin/`.

## Tests

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/utils_spec.lua"
```

Swap the filename for `anniversary_spec.lua` to run the other suite. See
`CLAUDE.md` for what each covers and what is still untested.
