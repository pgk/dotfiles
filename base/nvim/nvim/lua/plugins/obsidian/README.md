# obsidian/ — Obsidian-style notes workflow for Neovim

Custom Zettelkasten workflow built on
[obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim), for the
private vault at `~/notes`. Most of the interesting logic lives in five
stdlib-only Python CLI tools in dotfiles' `bin/` (`notes-graph`,
`notes-deadlinks`, `notes-similar`, `notes-embed-setup`); this plugin is a
thin Lua layer that wires their `--json` output into fzf-lua pickers.

- **Full user-facing docs, keybindings, and commands:**
  [`../../../obsidian-workflow.md`](../../../obsidian-workflow.md)
- **Development rules for this directory** — never touch the real vault,
  safety history, testing: [`CLAUDE.md`](CLAUDE.md)
- **In-editor help:** `:ObsidianHelp` / `<leader>oh` opens the doc above.

## Files

| File | Purpose |
|---|---|
| `init.lua` | Plugin spec — loads obsidian.nvim, wires up every module below, global keymaps |
| `utils.lua` | Shared helpers: vault path, safe `edit`/`write`, `sanitize`, `sample`, `run_notes_tool` |
| `commands.lua` | Misc commands: random note, insert link, rename, extract-to-note, help |
| `daily.lua` | Daily note template — on-this-day, neglected, and review sections |
| `anniversary.lua` | Date logic behind the "on this day" section |
| `panel.lua` | Links panel sidebar (forward links + backlinks) |
| `transclusion.lua` | Inline `![[note]]` rendering |
| `format.lua` | Custom `formatexpr` so `gw`/`gq` cannot break a `[[wiki link]]` across lines |
| `graph.lua` | Orphan/sparse/splittable notes and hubless clusters (`:ObsidianGraphHealth`) |
| `deadlinks.lua` | Dead `[[links]]` with fuzzy-matched candidates (`:ObsidianDeadLinks`) |
| `similar.lua` | Semantically similar but unlinked notes, via a local embedding server (`:ObsidianSimilar`) |
| `activity.lua` | Recently touched notes, grouped by link community (`:ObsidianActive`) |

`dev-vault/` is a permanent synthetic fixture — never the real vault — used
by both the Lua specs here and the Python tests in `bin/`.

## Tests

```sh
nvim --headless \
  -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
  -c "set rtp+=$PWD/base/nvim/nvim" \
  -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/obsidian/utils_spec.lua"
```

Swap the filename for `anniversary_spec.lua` to run the other suite. See
`CLAUDE.md` for what each covers and what is still untested.
