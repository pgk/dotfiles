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
| `<leader>ob` | `:ObsidianBacklinks` | Backlinks in picker |
| `<leader>of` | `:ObsidianLinks` | Forward links in picker |
| `<leader>ot` | `:ObsidianTransclusionToggle` | Toggle transclusion rendering |
| `<leader>oR` | `:ObsidianRename` | Rename note and update all links |

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
| `:ObsidianTransclusionToggle` | Toggle inline transclusion rendering |
| `:ObsidianRename [name]` | Rename current note and update all links |
| `:ObsidianDaily [offset]` | Open daily note with template (offset: -1 = yesterday) |

## Links Panel

The links panel (`<leader>ol`) shows a sidebar with:

- **Forward Links**: Notes linked from the current note, with preview text
- **Backlinks**: Notes that link to the current note, with context

The panel updates automatically when you switch buffers. Navigate to a link and press `<CR>` to open it.

## Daily Notes Workflow

New daily notes are automatically created with a template:

```markdown
# 2025-01-15

Previous: [[2025-01-13]]

## Review

- [[random-note-1]]
- [[random-note-2]]
- [[random-note-3]]
- [[random-note-4]]
- [[random-note-5]]

## Notes

```

Features:
- Links to the **previous daily note** (not yesterday, but the last existing entry)
- 5 random notes for review
- Ready-to-use structure

Workflow:
1. `<leader>od` - Open/create today's note
2. Review the random notes, add thoughts
3. Use `<leader>oi` to insert links to related notes

## Renaming Notes

Use `<leader>oR` or `:ObsidianRename` to rename the current note:
- Prompts for new name (pre-filled with current name)
- Renames the file
- Updates all `[[links]]` across the vault automatically

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

## Transclusion

Use `![[note-name]]` syntax to embed another note's content. Toggle rendering with `<leader>ot`.

When enabled, transclusions render as:
```
![[some-note]]
  ┌─ some-note
  │ First line of the note...
  │ Second line...
  │ ...
  └────────────────────────────────────────
```

- Content is read-only (virtual text)
- Shows entire file content
- Skips YAML frontmatter
- Wraps long lines to fit window
- Markdown highlighting (headers, lists, links, bold)
- Auto-updates as you edit

## Markdown Settings

- Soft word wrap enabled (visual only, no hard breaks)
- Line break at word boundaries
- Indent preserved on wrapped lines

## File Structure

Daily notes are created as `YYYY-MM-DD.md` directly in `~/notes` (no subfolder).
