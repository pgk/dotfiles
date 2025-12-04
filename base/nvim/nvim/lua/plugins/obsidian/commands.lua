-- Miscellaneous commands for Obsidian integration
local utils = require("plugins.obsidian.utils")

local M = {}

function M.random()
  local handle = io.popen('find "' .. utils.vault_path .. '" -name "*.md" -type f')
  if not handle then
    vim.notify("Failed to search vault", vim.log.levels.ERROR)
    return
  end
  local result = handle:read("*a")
  handle:close()

  local files = {}
  for file in result:gmatch("[^\n]+") do
    table.insert(files, file)
  end

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
  local handle = io.popen('grep -rilF -- "' .. search_term .. '" "' .. utils.vault_path .. '" --include="*.md" 2>/dev/null')
  local files_to_update = {}
  if handle then
    local result = handle:read("*a")
    handle:close()
    for file in result:gmatch("[^\n]+") do
      table.insert(files_to_update, file)
    end
  end

  vim.notify("Found " .. #files_to_update .. " files with links", vim.log.levels.INFO)

  -- Update links in all files (case-insensitive replace)
  local updated_count = 0
  local old_name_escaped = utils.escape_pattern(old_name)

  for _, filepath in ipairs(files_to_update) do
    local file = io.open(filepath, "r")
    if file then
      local content = file:read("*a")
      file:close()

      -- Replace [[old_name]] and [[old_name|alias]] (case-insensitive)
      local new_content = content:gsub("%[%[" .. old_name_escaped .. "%]%]", "[[" .. new_name .. "]]")
      new_content = new_content:gsub("%[%[" .. old_name_escaped .. "|", "[[" .. new_name .. "|")
      -- Also try case-insensitive by lowercasing comparison
      new_content = new_content:gsub("%[%[([^%]|]+)%]%]", function(match)
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

      if new_content ~= content then
        local out_file = io.open(filepath, "w")
        if out_file then
          out_file:write(new_content)
          out_file:close()
          updated_count = updated_count + 1
        end
      end
    end
  end

  -- Update id: in frontmatter in the current buffer
  local buf_lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local old_name_pattern = old_name:gsub("%-", "%%-")
  for i, line in ipairs(buf_lines) do
    if line:match("^id:%s*" .. old_name_pattern .. "$") then
      buf_lines[i] = "id: " .. new_name
      vim.api.nvim_buf_set_lines(0, 0, -1, false, buf_lines)
      break
    end
  end

  -- Rename the file
  vim.cmd("write " .. vim.fn.fnameescape(new_file))
  vim.fn.delete(current_file)
  vim.bo.modified = false
  vim.cmd("edit " .. vim.fn.fnameescape(new_file))
  vim.cmd("bdelete! #")

  vim.notify("Renamed to " .. new_name .. ", updated " .. updated_count .. " files", vim.log.levels.INFO)
end

-- Smart follow link - works even when cursor is on [[ or ]]
function M.smart_follow_link()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1 -- 1-indexed

  -- Find all [[link]] patterns in the line
  for start_pos, link, end_pos in line:gmatch("()%[%[([^%]|]+)[^%]]*%]%]()") do
    -- Check if cursor is anywhere within [[ and ]]
    if col >= start_pos and col <= end_pos - 1 then
      local handle = io.popen('find "' .. utils.vault_path .. '" -iname "' .. link .. '.md" -type f | head -1')
      if handle then
        local result = handle:read("*a"):gsub("\n", "")
        handle:close()
        if result ~= "" then
          vim.cmd("edit " .. vim.fn.fnameescape(result))
          return
        end
      end
      -- Note doesn't exist - create it
      local new_file = utils.vault_path .. "/" .. link .. ".md"
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
end

return M
