-- "On this day": notes whose date falls on today's month and day in an earlier year.
--
-- A note's date comes from its filename where it has one, and otherwise from its
-- mtime. Creation time is deliberately not consulted: whether this vault's sync
-- preserves birthtime has never been measured, and the rule for `--since` applies
-- here too — don't build on an unmeasured property of the sync setup.
local M = {}

local function iso(year, month, day)
  year, month, day = tonumber(year), tonumber(month), tonumber(day)
  if not year or not month or not day then
    return nil
  end
  if month < 1 or month > 12 or day < 1 or day > 31 then
    return nil
  end
  return string.format("%04d-%02d-%02d", year, month, day)
end

-- Anchored so a date has to open the name: "notes-on-2024-03-05" is a note
-- about a date, not a note from one.
local NAME_PATTERNS = {
  -- The 00YYYYMMDD-N form the old mknote script wrote. It needs its own pattern
  -- because no other one matches it: read as a bare YYYYMMDD the stem has a
  -- digit where the separator belongs, so that pattern fails outright.
  "^00(%d%d%d%d)(%d%d)(%d%d)[%-_ ]",
  "^00(%d%d%d%d)(%d%d)(%d%d)$",
  "^(%d%d%d%d)%-(%d%d)%-(%d%d)$",
  "^(%d%d%d%d)%-(%d%d)%-(%d%d)[%-_ ]",
  "^(%d%d%d%d)(%d%d)(%d%d)$",
  "^(%d%d%d%d)(%d%d)(%d%d)[%-_ ]",
}

function M.date_from_name(stem)
  if type(stem) ~= "string" or stem == "" then
    return nil
  end
  for _, pattern in ipairs(NAME_PATTERNS) do
    local year, month, day = stem:match(pattern)
    if year then
      return iso(year, month, day)
    end
  end
  return nil
end

local function split_date(text)
  if type(text) ~= "string" then
    return nil
  end
  local year, month_day = text:match("^(%d%d%d%d)%-(%d%d%-%d%d)$")
  if not year then
    return nil
  end
  return tonumber(year), month_day
end

-- entries: { { name, path, name_date, mtime_date }, ... }; today: "YYYY-MM-DD".
function M.on_this_day(entries, today)
  local hits = {}
  local this_year, today_month_day = split_date(today)
  if not this_year then
    return hits
  end

  for _, entry in ipairs(entries or {}) do
    -- One source per note, chosen before it is tested. The filename is the
    -- note's own claim about when it was written, so a note that carries one
    -- never falls back to mtime -- otherwise a note named 2024-09-15 could be
    -- listed on September 1st, contradicting the name shown beside it.
    local raw = entry.name_date or entry.mtime_date
    local source = entry.name_date and "name" or "mtime"
    local year, month_day = split_date(raw)
    if year and month_day == today_month_day and year < this_year then
      table.insert(hits, {
        name = entry.name,
        path = entry.path,
        date = raw,
        source = source,
        years_ago = this_year - year,
      })
    end
  end

  table.sort(hits, function(a, b)
    if a.years_ago ~= b.years_ago then
      return a.years_ago < b.years_ago
    end
    return a.name < b.name
  end)
  return hits
end

-- Build the entry list M.on_this_day expects from vault file paths.
--
-- `vault` bounds what may be stat'd. utils.list_note_files splits find(1) output
-- on newlines, so a note named "x\n/etc/hosts" yields a second path outside the
-- vault; without this an arbitrary absolute path would be stat'd and its mtime
-- could put its basename in the daily note.
function M.entries_for(files, vault)
  local entries = {}
  local prefix = vault and (vault:gsub("/+$", "") .. "/") or nil
  for _, path in ipairs(files) do
    local full = vim.fn.fnamemodify(path, ":p")
    if not prefix or full:sub(1, #prefix) == prefix then
      local stat = (vim.uv or vim.loop).fs_stat(path)
      if stat then
        local stem = vim.fn.fnamemodify(path, ":t:r")
        table.insert(entries, {
          name = stem,
          path = path,
          name_date = M.date_from_name(stem),
          mtime_date = os.date("%Y-%m-%d", stat.mtime.sec),
        })
      end
    end
  end
  return entries
end

return M
