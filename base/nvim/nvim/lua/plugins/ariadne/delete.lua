-- Deleting the current note, with a gate on the links that would break.
local utils = require("plugins.ariadne.utils")
local wikilinks = require("plugins.ariadne.wikilinks")

local M = {}

local sanitize = utils.sanitize
local TRASH = ".trash"
local LISTED = 8

-- nvim resolves a buffer's name through symlinks, so the buffer path and a
-- configured vault path need not share a prefix even when the file really is in
-- the vault -- on macOS a vault under /var is reported under /private/var. Every
-- comparison here is between resolved paths for that reason.
local function resolved(path)
  if type(path) ~= "string" or path == "" then
    return path
  end
  return ((vim.uv or vim.loop).fs_realpath(path)) or path
end

local function read_file(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local content = f:read("*a")
  f:close()
  return content
end

-- Notes that link to `name`, resolved exactly.
--
-- grep is only a prefilter, and it searches for the bare name rather than
-- `[[name` so that `[[dir/name]]` and a differently-cased `[[Name]]` are still
-- offered up — `utils.get_backlinks` searches the bracketed prefix and misses
-- both, which is survivable for a sidebar and not for a delete. Every candidate
-- is then re-checked with the real resolution rules, so prose mentions and
-- `[[name-of-something-else]]` fall out again.
local function linking_notes(path, name)
  local found = {}
  for _, candidate in ipairs(utils.grep_note_files(name, { ignorecase = true })) do
    if resolved(candidate) ~= path then
      local text = read_file(candidate)
      local count = text and wikilinks.count_to(text, name) or 0
      if count > 0 then
        table.insert(found, { path = candidate, name = utils.get_note_name(candidate), count = count })
      end
    end
  end
  table.sort(found, function(a, b)
    return a.name:lower() < b.name:lower()
  end)
  return found
end

local function describe_links(linked)
  local total = 0
  for _, entry in ipairs(linked) do
    total = total + entry.count
  end
  local lines = { string.format("%d link(s) in %d note(s) point here:", total, #linked) }
  for i, entry in ipairs(linked) do
    if i > LISTED then
      table.insert(lines, string.format("  ... and %d more", #linked - LISTED))
      break
    end
    table.insert(lines, string.format("  %s (%d)", sanitize(entry.name), entry.count))
  end
  return table.concat(lines, "\n"), total
end

-- A free path in the vault's `.trash/`. Every tool skips dot-prefixed
-- directories, so a note in there is gone as far as the graph is concerned but
-- is still a `mv` away from coming back.
local function trash_path(vault, basename)
  local dir = vault .. "/" .. TRASH
  if vim.fn.isdirectory(dir) == 0 and vim.fn.mkdir(dir, "p") == 0 then
    return nil, "could not create " .. TRASH .. "/"
  end
  local stem = basename:gsub("%.md$", "")
  local candidate = dir .. "/" .. basename
  local n = 0
  while vim.fn.filereadable(candidate) == 1 or vim.fn.isdirectory(candidate) == 1 do
    n = n + 1
    candidate = string.format("%s/%s-%d.md", dir, stem, n)
  end
  return candidate
end

local function unwrap_in(linked, name)
  local notes, links = 0, 0
  for _, entry in ipairs(linked) do
    local text = read_file(entry.path)
    if text then
      local rewritten, n = wikilinks.unwrap(text, name)
      if n > 0 and rewritten ~= text then
        local out = io.open(entry.path, "w")
        if out then
          out:write(rewritten)
          out:close()
          notes = notes + 1
          links = links + n
        else
          vim.notify("Could not rewrite " .. sanitize(entry.name), vim.log.levels.WARN)
        end
      end
    end
  end
  -- Buffers already open on a rewritten note still hold the old text, and
  -- writing one back would undo the rewrite.
  vim.cmd("checktime")
  return notes, links
end

local function validate(path, vault)
  if path == "" or not path:match("%.md$") then
    return "Not a markdown file"
  end
  if vim.fn.filereadable(path) == 0 then
    return "No such file on disk"
  end
  if not vim.startswith(path, vault .. "/") then
    return "Not a note in " .. vault
  end
  if vim.startswith(path, vault .. "/" .. TRASH .. "/") then
    return "Already in " .. TRASH .. "/"
  end
  return nil
end

function M.delete()
  local path = resolved(vim.api.nvim_buf_get_name(0))
  local vault = resolved(utils.vault_path)
  local problem = validate(path, vault)
  if problem then
    vim.notify(problem, vim.log.levels.WARN)
    return
  end

  local name = utils.get_note_name(path)
  local linked = linking_notes(path, name)
  local summary, total = describe_links(linked)
  if #linked > 0 then
    local prompt = string.format("Delete '%s'?\n\n%s", sanitize(name), summary)
    if vim.fn.confirm(prompt, "&Delete anyway\n&Cancel", 2, "Question") ~= 1 then
      vim.notify("Delete cancelled", vim.log.levels.INFO)
      return
    end
  end

  local dest, err = trash_path(vault, vim.fn.fnamemodify(path, ":t"))
  if not dest then
    vim.notify("Delete failed: " .. err, vim.log.levels.ERROR)
    return
  end
  local ok, move_err = (vim.uv or vim.loop).fs_rename(path, dest)
  if not ok then
    vim.notify("Delete failed: " .. sanitize(move_err or "could not move the file"), vim.log.levels.ERROR)
    return
  end
  vim.cmd("bdelete!")
  vim.notify(
    string.format("Moved %s to %s/", sanitize(name), TRASH),
    vim.log.levels.INFO
  )

  if #linked == 0 then
    return
  end
  local prompt = string.format("%d link(s) in %d note(s) now dangle. Unwrap them to plain text?", total, #linked)
  if vim.fn.confirm(prompt, "&Unwrap\n&Leave them", 2, "Question") ~= 1 then
    vim.notify("Left " .. total .. " dangling link(s) -- :AriadneDeadLinks to review", vim.log.levels.INFO)
    return
  end
  local notes, links = unwrap_in(linked, name)
  vim.notify(string.format("Unwrapped %d link(s) in %d note(s)", links, notes), vim.log.levels.INFO)
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneDelete", function()
    M.delete()
  end, { desc = "Move the current note to the vault's .trash/, checking what links to it" })
end

return M
