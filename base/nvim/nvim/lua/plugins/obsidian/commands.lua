-- Miscellaneous commands for Obsidian integration
local utils = require("plugins.obsidian.utils")

local M = {}

function M.random()
  local files = utils.list_note_files()

  if #files == 0 then
    vim.notify("No notes found in vault", vim.log.levels.WARN)
    return
  end

  math.randomseed(os.time())
  local random_file = files[math.random(#files)]
  vim.cmd("edit " .. vim.fn.fnameescape(random_file))
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
local function rewrite_links(filepath, old_name, new_name)
  local file = io.open(filepath, "r")
  if not file then
    return false
  end
  local content = file:read("*a")
  file:close()

  local new_content = content:gsub("%[%[([^%]|]+)%]%]", function(match)
    if match:lower() == old_name:lower() then
      return "[[" .. new_name .. "]]"
    end
    return "[[" .. match .. "]]"
  end)
  new_content = new_content:gsub("%[%[([^%]|]+)|", function(match)
    if match:lower() == old_name:lower() then
      return "[[" .. new_name .. "|"
    end
    return "[[" .. match .. "|"
  end)

  if new_content == content then
    return false
  end
  local out_file = io.open(filepath, "w")
  if not out_file then
    return false
  end
  out_file:write(new_content)
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

function M.rename(new_name)
  local current_file = vim.api.nvim_buf_get_name(0)
  if not current_file:match("%.md$") then
    vim.notify("Not a markdown file", vim.log.levels.ERROR)
    return
  end

  local old_name = vim.fn.fnamemodify(current_file, ":t:r")

  if new_name == "" then
    new_name = vim.fn.input("New name: ", old_name)
    if new_name == "" or new_name == old_name then
      vim.notify("Rename cancelled", vim.log.levels.INFO)
      return
    end
  end

  -- New file path
  local new_file = vim.fn.fnamemodify(current_file, ":h") .. "/" .. new_name .. ".md"

  -- Check if target exists
  if vim.fn.filereadable(new_file) == 1 then
    vim.notify("File already exists: " .. new_name, vim.log.levels.ERROR)
    return
  end

  -- Find all files that link to the old name (case-insensitive)
  local search_term = "[[" .. old_name
  local files_to_update = utils.grep_note_files(search_term, { ignorecase = true })
  vim.notify("Found " .. #files_to_update .. " files with links", vim.log.levels.INFO)

  local updated_count = 0
  for _, filepath in ipairs(files_to_update) do
    if rewrite_links(filepath, old_name, new_name) then
      updated_count = updated_count + 1
    end
  end

  update_frontmatter_id(old_name, new_name)

  -- Rename the file
  vim.cmd("write " .. vim.fn.fnameescape(new_file))
  vim.fn.delete(current_file)
  vim.bo.modified = false
  vim.cmd("edit " .. vim.fn.fnameescape(new_file))
  vim.cmd("bdelete! #")

  vim.notify("Renamed to " .. new_name .. ", updated " .. updated_count .. " files", vim.log.levels.INFO)
end

-- Extract selection to new note
function M.extract_note()
  -- Get visual selection
  local start_pos = vim.fn.getpos("'<")
  local end_pos = vim.fn.getpos("'>")
  local start_line, start_col = start_pos[2], start_pos[3]
  local end_line, end_col = end_pos[2], end_pos[3]

  local lines = vim.api.nvim_buf_get_lines(0, start_line - 1, end_line, false)
  if #lines == 0 then
    vim.notify("No text selected", vim.log.levels.WARN)
    return
  end

  -- Clamp end_col to actual line length (handles V and $ selections)
  local last_line_len = #lines[#lines]
  if end_col > last_line_len then
    end_col = last_line_len
  end

  -- Adjust for partial line selection
  if #lines == 1 then
    lines[1] = lines[1]:sub(start_col, end_col)
  else
    lines[1] = lines[1]:sub(start_col)
    lines[#lines] = lines[#lines]:sub(1, end_col)
  end

  local selected_text = table.concat(lines, "\n")

  -- Prompt for note name
  local note_name = vim.fn.input("New note name: ")
  if note_name == "" then
    vim.notify("Extract cancelled", vim.log.levels.INFO)
    return
  end

  -- Check if note already exists
  local new_file = utils.vault_path .. "/" .. note_name .. ".md"
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

  -- Replace selection with link
  local link = "[[" .. note_name .. "]]"
  vim.api.nvim_buf_set_text(0, start_line - 1, start_col - 1, end_line - 1, end_col, { link })

  vim.notify("Extracted to: " .. note_name, vim.log.levels.INFO)
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
        vim.cmd("edit " .. vim.fn.fnameescape(found))
        return
      end
      -- Note doesn't exist - create it, but never outside the vault (a link
      -- like [[../../etc/passwd]] must not escape via this concatenation).
      local new_file = vim.fs.normalize(utils.vault_path .. "/" .. link .. ".md")
      if not vim.startswith(new_file, utils.vault_path .. "/") then
        vim.notify("Link escapes the vault: " .. link, vim.log.levels.WARN)
        return
      end
      vim.cmd("edit " .. vim.fn.fnameescape(new_file))
      vim.notify("Created: " .. link, vim.log.levels.INFO)
      return
    end
  end

  -- Fallback to default gf
  vim.cmd("normal! gf")
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianRandom", function()
    M.random()
  end, { desc = "Open a random note from vault" })

  vim.api.nvim_create_user_command("ObsidianInsertLink", function()
    M.insert_link()
  end, { desc = "Insert link via fulltext search" })

  vim.api.nvim_create_user_command("ObsidianRename", function(opts)
    M.rename(opts.args or "")
  end, { nargs = "?", desc = "Rename note and update links" })

  vim.api.nvim_create_user_command("ObsidianExtract", function()
    M.extract_note()
  end, { range = true, desc = "Extract selection to new note" })
end

return M
