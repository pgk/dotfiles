-- Deleting the current note, with a gate on the links that would break.
local backlinks = require("plugins.ariadne.backlinks")
local utils = require("plugins.ariadne.utils")
local wikilinks = require("plugins.ariadne.wikilinks")

local M = {}

local sanitize = utils.sanitize
-- Every path comparison below is between resolved paths; see utils.resolve.
local resolved = utils.resolve
local TRASH = ".trash"
local LISTED = 8

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

-- Unwrap only outside the managed backlinks blocks. The gate above counted
-- authored links, so unwrapping the whole text rewrote rows the gate never
-- warned about and reported more links than it had promised -- and an unwrapped
-- row (`- deleted-note`) is no longer a row, so the next `:AriadneBacklinks`
-- absorbed the corpse as an annotation of whichever row preceded it. A stale row
-- left alone is invisible to every tool and disappears on that refresh instead.
local function unwrap_authored(text, name)
  local lines = vim.split(text, "\n", { plain = true })
  local masked = {}
  for _, block in ipairs(backlinks.spans(lines)) do
    for i = block[1], block[2] do
      masked[i] = true
    end
  end
  local total = 0
  for i, line in ipairs(lines) do
    if not masked[i] then
      local rewritten, n = wikilinks.unwrap(line, name)
      lines[i] = rewritten
      total = total + n
    end
  end
  return table.concat(lines, "\n"), total
end

local function unwrap_in(linked, name)
  local notes, links = 0, 0
  for _, entry in ipairs(linked) do
    local text = utils.read_note(entry.path)
    if text then
      local rewritten, n = unwrap_authored(text, name)
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
  if not utils.in_vault(path) then
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
  -- `backlinks.linking_notes` is the exact resolver this and the links panel
  -- share: grep as a prefilter on the bare name, then the real resolution rules
  -- on each candidate's authored text. Both the prompt below and the unwrap that
  -- follows depend on that exactness, which is why neither can use a
  -- bracket-prefix match.
  local linked = backlinks.linking_notes(path, name)
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
