-- Daily notes for Obsidian integration
local utils = require("plugins.obsidian.utils")
local anniversary = require("plugins.obsidian.anniversary")

local M = {}

math.randomseed((vim.uv or vim.loop).hrtime())

local ON_THIS_DAY_LIMIT = 5
local NEGLECTED_WINDOW = "180d"
local NEGLECTED_SAMPLE = 3
-- Sampled from a pool rather than taken in rank order: the ranking is stable
-- between runs, so the same top rows would appear every morning until the notes
-- were edited -- and opening one without editing it does not move its mtime.
local NEGLECTED_POOL = 50

local function pick_sample(pool, count)
  local picked, taken = {}, {}
  while #picked < count and #picked < #pool do
    local idx = math.random(#pool)
    if not taken[idx] then
      taken[idx] = true
      table.insert(picked, pool[idx])
    end
  end
  return picked
end

local function on_this_day_lines(today_str)
  local vault = utils.vault_path
  local entries = anniversary.entries_for(utils.list_note_files(), vault)
  local hits = anniversary.on_this_day(entries, today_str)
  if #hits == 0 then
    return {}
  end
  local lines = { "## On this day", "" }
  for i, hit in ipairs(hits) do
    if i > ON_THIS_DAY_LIMIT then
      break
    end
    local years = hit.years_ago == 1 and "1 year ago" or (hit.years_ago .. " years ago")
    table.insert(lines, string.format("- %s (%s)", utils.as_wikilink(hit.name), years))
  end
  if #hits > ON_THIS_DAY_LIMIT then
    table.insert(lines, string.format("- ...and %d older", #hits - ON_THIS_DAY_LIMIT))
  end
  table.insert(lines, "")
  return lines
end

local function neglected_pool()
  if vim.fn.executable("notes-graph") == 0 then
    vim.notify("notes-graph not found on PATH; skipping the neglected section", vim.log.levels.WARN)
    return nil
  end
  local argv = {
    "notes-graph", utils.vault_path,
    "--neglected", NEGLECTED_WINDOW,
    "--limit", tostring(NEGLECTED_POOL),
    "--json",
  }
  local result = vim.system(argv, { text = true }):wait(30000)
  local output = result.stdout or ""
  if result.stderr and result.stderr ~= "" then
    vim.notify("notes-graph: " .. utils.sanitize(result.stderr), vim.log.levels.WARN)
  end
  local ok, decoded = pcall(vim.json.decode, output)
  if result.code ~= 0 or not ok or type(decoded) ~= "table" or type(decoded.neglected) ~= "table" then
    local detail = output == "" and "(no output)" or output:sub(1, 200)
    vim.notify(
      "notes-graph --neglected failed, skipping that section: " .. utils.sanitize(detail),
      vim.log.levels.WARN
    )
    return nil
  end
  -- Shape-check every row. An unexpected type would otherwise throw out of
  -- M.open, and the daily note would not be written at all.
  local pool = {}
  for _, entry in ipairs(decoded.neglected) do
    if type(entry) == "table" and type(entry.name) == "string" and type(entry.degree) == "number" then
      table.insert(pool, entry)
    end
  end
  return pool
end

local function neglected_lines()
  local pool = neglected_pool()
  if not pool or #pool == 0 then
    return {}
  end
  local picked = pick_sample(pool, NEGLECTED_SAMPLE)
  table.sort(picked, function(a, b)
    return a.degree > b.degree
  end)
  local lines = { "## Neglected", "" }
  for _, entry in ipairs(picked) do
    local degree = entry.degree
    table.insert(lines, string.format(
      "- %s - %d %s, untouched %s",
      utils.as_wikilink(entry.name), degree, degree == 1 and "link" or "links",
      type(entry.age) == "string" and utils.sanitize(entry.age) or "?"
    ))
  end
  table.insert(lines, "")
  return lines
end

local function find_previous_daily_note(today_str)
  -- Find all daily notes (YYYY-MM-DD.md pattern)
  local files = utils.list_note_files({ maxdepth = 1, name = "????-??-??.md" })
  table.sort(files, function(a, b) return a > b end)

  for _, file in ipairs(files) do
    local date_str = vim.fn.fnamemodify(file, ":t:r")
    if date_str < today_str then
      return date_str
    end
  end
  return nil
end

local function get_random_review_notes(today_str, count)
  local files = {}
  local today_filename = today_str .. ".md"
  for _, file in ipairs(utils.list_note_files()) do
    local filename = vim.fn.fnamemodify(file, ":t")
    if filename ~= today_filename then
      table.insert(files, file)
    end
  end

  if #files < count then
    count = #files
  end

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
    table.insert(lines, "Daily note for " .. today_str)
    table.insert(lines, "")

    -- Link to previous daily note
    local prev_daily = find_previous_daily_note(today_str)
    if prev_daily then
      table.insert(lines, "Previous #daily-note was: [[" .. prev_daily .. "]]")
      table.insert(lines, "")
    end

    -- Add random notes for review
    table.insert(lines, "")
    local random_notes = get_random_review_notes(today_str, 5)
    for _, note in ipairs(random_notes) do
      table.insert(lines, "- [[" .. note .. "]]")
    end
    table.insert(lines, "")

    vim.list_extend(lines, on_this_day_lines(today_str))
    vim.list_extend(lines, neglected_lines())

    -- Write file
    local file = io.open(daily_file, "w")
    if file then
      file:write(table.concat(lines, "\n"))
      file:close()
    end
  end

  utils.edit(daily_file)
end

function M.add_review()
  local today = os.date("%Y-%m-%d")
  local daily_note_path = utils.vault_path .. "/" .. today .. ".md"

  -- Get all markdown files
  local all_files = utils.list_note_files()

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
  for _, file in ipairs(all_files) do
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
