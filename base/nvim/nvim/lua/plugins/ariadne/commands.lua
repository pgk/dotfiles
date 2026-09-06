-- Miscellaneous commands for the Ariadne notes workflow
local selection = require("plugins.ariadne.selection")
local utils = require("plugins.ariadne.utils")
local wikilinks = require("plugins.ariadne.wikilinks")

local M = {}

-- Computed from this file's own location rather than hardcoded, so a plugin-dir
-- reshuffle can't silently point :AriadneHelp at a stale path. commands.lua
-- sits at .../nvim/lua/plugins/ariadne/commands.lua; the doc lives at
-- .../nvim/ariadne.md, four path components up.
local HELP_DOC = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":h:h:h:h") .. "/ariadne.md"

function M.help()
  if vim.fn.filereadable(HELP_DOC) == 0 then
    vim.notify("Workflow doc not found: " .. HELP_DOC, vim.log.levels.WARN)
    return
  end
  utils.edit(HELP_DOC)
end

function M.random()
  local files = utils.list_note_files()

  if #files == 0 then
    vim.notify("No notes found in vault", vim.log.levels.WARN)
    return
  end

  utils.edit(utils.sample(files, 1)[1])
end

function M.insert_link()
  local fzf = require("fzf-lua")

  fzf.grep({
    cwd = utils.vault_path,
    search = "",
    filespec = "*.md",
    prompt = "Insert link> ",
    actions = {
      ["default"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        -- Extract filename from selection (format: "file:line:content")
        local file = selected[1]:match("^([^:]+)")
        if file then
          local note_name = vim.fn.fnamemodify(file, ":t:r")
          local link = "[[" .. note_name .. "]]"
          vim.api.nvim_put({ link }, "c", true, true)
        end
      end,
    },
  })
end

-- Rewrite [[old_name]] / [[old_name|alias]] links to new_name (case-insensitive).
-- Returns true if the file was changed.
-- Point every link to `old_name` at `new_name`, in one note on disk.
--
-- The grammar lives in wikilinks, not here: this used to compare the raw
-- bracketed text, so `[[dir/note]]` and `[[note#heading]]` were left pointing at
-- the renamed-away note -- and rename deletes the original, so those became dead
-- links. Same class of bug the delete gate was built to avoid.
local function rewrite_links(filepath, old_name, new_name)
  local content = utils.read_note(filepath)
  if not content then
    return false
  end
  local rewritten, n = wikilinks.retarget(content, old_name, new_name)
  if n == 0 or rewritten == content then
    return false
  end
  local out_file = io.open(filepath, "w")
  if not out_file then
    return false
  end
  out_file:write(rewritten)
  out_file:close()
  return true
end

-- Rename `id: old_name` to `id: new_name` in the current buffer's frontmatter, if present.
local function update_frontmatter_id(old_name, new_name)
  local buf_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local old_name_pattern = utils.escape_pattern(old_name)
  for i, line in ipairs(buf_lines) do
    if line:match("^id:%s*" .. old_name_pattern .. "$") then
      buf_lines[i] = "id: " .. new_name
      vim.api.nvim_buf_set_lines(0, 0, -1, false, buf_lines)
      return
    end
  end
end

-- `opts.dir` renames the note into another directory instead of the one it is
-- in: :AriadnePlace files a note beside the sequence it was just placed in, the
-- same rule branch.lua follows for a note it creates. Returns whether the note
-- was renamed: `place.lua` writes the parent link only on a true, and a write
-- can fail (see `utils.write`), so this is a real gate rather than decoration.
function M.rename(new_name, opts)
  opts = opts or {}
  local current_file = vim.api.nvim_buf_get_name(0)
  if not current_file:match("%.md$") then
    vim.notify("Not a markdown file", vim.log.levels.ERROR)
    return false
  end

  local old_name = vim.fn.fnamemodify(current_file, ":t:r")

  if new_name == "" then
    new_name = vim.fn.input("New name: ", old_name)
    if new_name == "" or new_name == old_name then
      vim.notify("Rename cancelled", vim.log.levels.INFO)
      return false
    end
  end

  -- vault_child, not a concatenation: `new_name` came from a prompt, so
  -- `../../elsewhere` used to place the note outside the directory being renamed
  -- in -- and rename deletes the original, so there was no copy left behind.
  local new_file = utils.vault_child(new_name, opts.dir or vim.fn.fnamemodify(current_file, ":h"))
  if not new_file then
    vim.notify("Name escapes its destination directory: " .. utils.sanitize(new_name), vim.log.levels.WARN)
    return false
  end

  -- Check if target exists
  if vim.fn.filereadable(new_file) == 1 then
    vim.notify("File already exists: " .. utils.sanitize(new_name), vim.log.levels.ERROR)
    return false
  end

  -- Find all files that link to the old name (case-insensitive)
  -- Bare name, not "[[name": the bracketed prefix never matches [[dir/name]],
  -- so retarget would never see it. grep is a prefilter; retarget re-checks.
  local files_to_update = utils.grep_note_files(old_name, { ignorecase = true })
  vim.notify("Found " .. #files_to_update .. " files with links", vim.log.levels.INFO)

  -- The destination is written BEFORE anything else is retargeted at it, and the
  -- order is load-bearing: the write is the step that can still fail (a
  -- destination directory that has gone away throws E212), and it used to run
  -- last. A failure there left the original note in place with every [[link]] in
  -- the vault already pointing at a name that did not exist -- a vault-wide dead
  -- link event, with no rollback. Now a failed write costs nothing but the
  -- frontmatter edit sitting unsaved in the buffer.
  --
  -- The frontmatter goes first because `utils.write` writes the *buffer*.
  update_frontmatter_id(old_name, new_name)
  if not utils.write(new_file) then
    return false
  end

  local updated_count = 0
  for _, filepath in ipairs(files_to_update) do
    if rewrite_links(filepath, old_name, new_name) then
      updated_count = updated_count + 1
    end
  end

  vim.fn.delete(current_file)
  vim.bo.modified = false
  utils.edit(new_file)
  vim.cmd("bdelete! #")

  vim.notify(
    "Renamed to " .. utils.sanitize(new_name) .. ", updated " .. updated_count .. " files",
    vim.log.levels.INFO
  )
  return true
end

-- Extract selection to new note.
--
-- The range is taken once and used for both halves: `selection.lua` was split
-- out of this function and the four range locals were left behind here,
-- undefined, so the replace step threw on every run -- after the new note had
-- already been written. Read the range, not just the text, or the two can
-- describe different regions.
function M.extract_note()
  local range = selection.visual_range()
  if not range then
    vim.notify("No text selected", vim.log.levels.WARN)
    return
  end
  local selected_text = selection.text_in(0, range)

  -- Prompt for note name
  local note_name = vim.fn.input("New note name: ")
  if note_name == "" then
    vim.notify("Extract cancelled", vim.log.levels.INFO)
    return
  end

  -- Guarded join: the name came from a prompt, so it must not escape the vault.
  local new_file = utils.vault_child(note_name)
  if not new_file then
    vim.notify("Name escapes the vault: " .. utils.sanitize(note_name), vim.log.levels.WARN)
    return
  end
  if vim.fn.filereadable(new_file) == 1 then
    vim.notify("Note already exists: " .. note_name, vim.log.levels.ERROR)
    return
  end

  -- Create new note with selected text
  local file = io.open(new_file, "w")
  if not file then
    vim.notify("Failed to create note", vim.log.levels.ERROR)
    return
  end
  file:write(selected_text .. "\n")
  file:close()

  -- Replace selection with link. as_wikilink rather than bare brackets: a name
  -- containing `]]` would close the link early and forge one to a note the
  -- writer never referenced.
  vim.api.nvim_buf_set_text(
    0, range.start_row, range.start_col, range.end_row, range.end_col,
    { utils.as_wikilink(note_name) }
  )

  vim.notify("Extracted to: " .. utils.sanitize(note_name), vim.log.levels.INFO)
end

-- Smart follow link - works even when cursor is on [[ or ]]
function M.smart_follow_link()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1 -- 1-indexed

  -- Find all [[link]] patterns in the line
  for start_pos, link, end_pos in line:gmatch("()%[%[([^%]|]+)[^%]]*%]%]()") do
    -- Check if cursor is anywhere within [[ and ]]
    if col >= start_pos and col <= end_pos - 1 then
      local found = utils.find_note_file(link)
      if found then
        utils.edit(found)
        return
      end
      -- Note doesn't exist - create it, but never outside the vault: a link
      -- like [[../../etc/passwd]] must not escape via this concatenation.
      local new_file = utils.vault_child(link)
      if not new_file then
        vim.notify("Link escapes the vault: " .. utils.sanitize(link), vim.log.levels.WARN)
        return
      end
      utils.edit(new_file)
      vim.notify("Created: " .. utils.sanitize(link), vim.log.levels.INFO)
      return
    end
  end

  -- Fallback to default gf
  vim.cmd("normal! gf")
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneRandom", function()
    M.random()
  end, { desc = "Open a random note from vault" })

  vim.api.nvim_create_user_command("AriadneInsertLink", function()
    M.insert_link()
  end, { desc = "Insert link via fulltext search" })

  vim.api.nvim_create_user_command("AriadneRename", function(opts)
    M.rename(opts.args or "")
  end, { nargs = "?", desc = "Rename note and update links" })

  vim.api.nvim_create_user_command("AriadneExtract", function()
    M.extract_note()
  end, { range = true, desc = "Extract selection to new note" })

  vim.api.nvim_create_user_command("AriadneHelp", function()
    M.help()
  end, { desc = "Open the workflow reference doc (ariadne.md)" })
end

return M
