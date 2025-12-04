-- Daily notes for Obsidian integration
local utils = require("plugins.obsidian.utils")

local M = {}

local function find_previous_daily_note(today_str)
  -- Find all daily notes (YYYY-MM-DD.md pattern)
  local handle = io.popen('find "' .. utils.vault_path .. '" -maxdepth 1 -name "????-??-??.md" -type f | sort -r')
  if not handle then
    return nil
  end
  local result = handle:read("*a")
  handle:close()

  for file in result:gmatch("[^\n]+") do
    local date_str = vim.fn.fnamemodify(file, ":t:r")
    if date_str < today_str then
      return date_str
    end
  end
  return nil
end

local function get_random_review_notes(today_str, count)
  local handle = io.popen('find "' .. utils.vault_path .. '" -name "*.md" -type f')
  if not handle then
    return {}
  end
  local result = handle:read("*a")
  handle:close()

  local files = {}
  local today_filename = today_str .. ".md"
  for file in result:gmatch("[^\n]+") do
    local filename = vim.fn.fnamemodify(file, ":t")
    if filename ~= today_filename then
      table.insert(files, file)
    end
  end

  if #files < count then
    count = #files
  end

  math.randomseed(os.time())
  local selected = {}
  local indices = {}
  while #selected < count and #selected < #files do
    local idx = math.random(#files)
    if not indices[idx] then
      indices[idx] = true
      local note_name = vim.fn.fnamemodify(files[idx], ":t:r")
      table.insert(selected, note_name)
    end
  end
  return selected
end

function M.open(offset)
  offset = offset or 0
  local date = os.time() + (offset * 24 * 60 * 60)
  local today_str = os.date("%Y-%m-%d", date)
  local daily_file = utils.vault_path .. "/" .. today_str .. ".md"

  local is_new = vim.fn.filereadable(daily_file) == 0

  if is_new then
    -- Create with template
    local lines = {}
    table.insert(lines, "# " .. today_str)
    table.insert(lines, "")

    -- Link to previous daily note
    local prev_daily = find_previous_daily_note(today_str)
    if prev_daily then
      table.insert(lines, "Previous: [[" .. prev_daily .. "]]")
      table.insert(lines, "")
    end

    -- Add random notes for review
    table.insert(lines, "## Review")
    table.insert(lines, "")
    local random_notes = get_random_review_notes(today_str, 5)
    for _, note in ipairs(random_notes) do
      table.insert(lines, "- [[" .. note .. "]]")
    end
    table.insert(lines, "")
    table.insert(lines, "## Notes")
    table.insert(lines, "")

    -- Write file
    local file = io.open(daily_file, "w")
    if file then
      file:write(table.concat(lines, "\n"))
      file:close()
    end
  end

  vim.cmd("edit " .. vim.fn.fnameescape(daily_file))
end

function M.add_review()
  local today = os.date("%Y-%m-%d")
  local daily_note_path = utils.vault_path .. "/" .. today .. ".md"

  -- Get all markdown files
  local handle = io.popen('find "' .. utils.vault_path .. '" -name "*.md" -type f')
  if not handle then
    vim.notify("Failed to search vault", vim.log.levels.ERROR)
    return
  end
  local result = handle:read("*a")
  handle:close()

  -- Get existing links in daily note to avoid duplicates
  local existing_links = {}
  local daily_file_read = io.open(daily_note_path, "r")
  if daily_file_read then
    local content = daily_file_read:read("*a")
    daily_file_read:close()
    for link in content:gmatch("%[%[([^%]|]+)") do
      existing_links[link] = true
    end
  end

  local files = {}
  local today_filename = today .. ".md"
  for file in result:gmatch("[^\n]+") do
    local filename = vim.fn.fnamemodify(file, ":t")
    local note_name = vim.fn.fnamemodify(file, ":t:r")
    -- Exclude today's daily note and already linked notes
    if filename ~= today_filename and not existing_links[note_name] then
      table.insert(files, file)
    end
  end

  if #files < 5 then
    vim.notify("Not enough notes in vault (need at least 5)", vim.log.levels.WARN)
    return
  end

  -- Pick 5 random unique notes
  math.randomseed(os.time())
  local selected = {}
  local indices = {}
  while #selected < 5 do
    local idx = math.random(#files)
    if not indices[idx] then
      indices[idx] = true
      local note_name = vim.fn.fnamemodify(files[idx], ":t:r")
      table.insert(selected, "- [[" .. note_name .. "]]")
    end
  end

  -- Append to daily note
  local daily_file = io.open(daily_note_path, "a")
  if not daily_file then
    vim.notify("Failed to open daily note", vim.log.levels.ERROR)
    return
  end
  daily_file:write("\n## Review\n\n")
  daily_file:write(table.concat(selected, "\n") .. "\n")
  daily_file:close()

  vim.notify("Added 5 random notes to daily review")

  -- Reload if daily note is open
  local current_file = vim.fn.expand("%:p")
  if current_file == daily_note_path then
    vim.cmd("edit!")
  end
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianDaily", function(opts)
    local offset = tonumber(opts.args) or 0
    M.open(offset)
  end, { nargs = "?", desc = "Open daily note with template" })

  vim.api.nvim_create_user_command("ObsidianDailyReview", function()
    M.add_review()
  end, { desc = "Add 5 random notes to daily note for review" })
end

return M
