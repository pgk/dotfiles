# Obsidian Workflow in Neovim

This document describes the custom Obsidian integration for Neovim, built on top of [obsidian.nvim](https://github.com/obsidian-nvim/obsidian.nvim).

## Vault Location

`~/notes`

## Keybindings

### Global (available anywhere after startup)

| Key | Command | Description |
|-----|---------|-------------|
| `<leader>od` | `:ObsidianToday` | Open today's daily note |
| `<leader>or` | `:ObsidianRandom` | Open a random note |
| `<leader>ol` | `:ObsidianLinksPanel` | Toggle links panel sidebar |
| `<leader>os` | `:ObsidianSearch` | Search vault (fulltext) |
| `<leader>on` | `:ObsidianNew` | Create a new note |
| `<leader>oi` | `:ObsidianInsertLink` | Search vault and insert link at cursor |

### In Markdown Files

| Key | Description |
|-----|-------------|
| `gf` | Smart follow link (works on `[[` or `]]` too) |
| `<leader>ch` | Toggle checkbox |
| `[[` | Triggers completion for note links |

### In Links Panel

| Key | Description |
|-----|-------------|
| `<CR>` / `o` / `gf` | Open link under cursor |
| `q` | Close panel |
| `<C-w>h` | Return to main window |

## Commands

| Command | Description |
|---------|-------------|
| `:ObsidianToday [offset]` | Open daily note (offset: -1 = yesterday, 1 = tomorrow) |
| `:ObsidianRandom` | Open a random note from vault |
| `:ObsidianLinksPanel` | Toggle the links panel sidebar |
| `:ObsidianSearch` | Fulltext search across vault |
| `:ObsidianNew` | Create a new note |
| `:ObsidianInsertLink` | Search and insert a `[[link]]` at cursor |
| `:ObsidianDailyReview` | Add 5 random notes to today's daily note |
| `:ObsidianBacklinks` | Show backlinks in picker (built-in) |
| `:ObsidianLinks` | Show forward links in picker (built-in) |

## Links Panel

The links panel (`<leader>ol`) shows a sidebar with:

- **Forward Links**: Notes linked from the current note, with preview text
- **Backlinks**: Notes that link to the current note, with context

The panel updates automatically when you switch buffers. Navigate to a link and press `<CR>` to open it.

## Daily Notes Workflow

1. `<leader>od` - Open today's note
2. `:ObsidianDailyReview` - Add 5 random notes for review (excludes already-linked notes)
3. Review each linked note, add thoughts
4. Use `<leader>oi` to insert links to related notes

## Quick Capture Workflow

1. `<leader>on` - Create a new note
2. Write your content
3. Use `[[` to link to existing notes (completion available)
4. Or use `<leader>oi` to search and insert links

## Navigation Workflow

1. Open any note
2. `<leader>ol` - Open links panel to see connections
3. `<C-w>l` - Focus the panel
4. Navigate to a link, press `<CR>` to open
5. `gf` on any `[[link]]` in the main editor to follow

## Markdown Settings

- Soft word wrap enabled (visual only, no hard breaks)
- Line break at word boundaries
- Indent preserved on wrapped lines

## File Structure

Daily notes are created as `YYYY-MM-DD.md` directly in `~/notes` (no subfolder).
