-- Creating the next note in a Folgezettel sequence, from the one you are in.
local utils = require("plugins.ariadne.utils")
local folgezettel = require("plugins.ariadne.folgezettel")

local M = {}

-- Every id already in use, lowercased. Read from filenames rather than from an
-- index, so a note created outside the editor still reserves its number.
local function taken_ids()
  local taken = {}
  for _, path in ipairs(utils.list_note_files()) do
    local id = folgezettel.split(utils.get_note_name(path))
    if id then
      taken[id:lower()] = true
    end
  end
  return taken
end

local KINDS = {
  child = { first = folgezettel.child, lead = "Branched from" },
  -- A sibling continues the line it is part of; it did not branch off the note
  -- before it, so it does not say it did.
  sibling = { first = folgezettel.sibling, lead = "Continues" },
}

function M.create(kind)
  local spec = KINDS[kind]
  local path = utils.resolve(vim.api.nvim_buf_get_name(0))
  if not utils.in_vault(path) or not path:match("%.md$") then
    vim.notify("Not a note in " .. utils.vault_path, vim.log.levels.WARN)
    return
  end

  local parent = utils.get_note_name(path)
  local id = folgezettel.split(parent)
  if not id then
    vim.notify(
      utils.sanitize(parent) .. " has no Folgezettel id to branch from",
      vim.log.levels.WARN
    )
    return
  end

  local new_id = folgezettel.first_free(spec.first(id), taken_ids())
  local title = vim.trim(vim.fn.input(new_id .. " "))
  if title == "" then
    vim.notify("Cancelled", vim.log.levels.INFO)
    return
  end

  -- Beside the parent, not at the vault root: a branch belongs with the
  -- sequence it continues.
  local dir = vim.fn.fnamemodify(path, ":h")
  local new_path = utils.vault_child(new_id .. " " .. title, dir)
  if not new_path then
    vim.notify("Title escapes the vault: " .. utils.sanitize(title), vim.log.levels.WARN)
    return
  end
  if vim.fn.filereadable(new_path) == 1 then
    vim.notify("Note already exists: " .. utils.sanitize(new_id .. " " .. title), vim.log.levels.ERROR)
    return
  end

  -- The id only implies the relationship; ariadne-graph counts wikilinks, so
  -- without this line every branched note reads as an orphan.
  local body = spec.lead .. " " .. utils.as_wikilink(parent) .. "\n\n"
  local out = io.open(new_path, "w")
  if not out then
    vim.notify("Could not create " .. utils.sanitize(new_id), vim.log.levels.ERROR)
    return
  end
  out:write(body)
  out:close()

  utils.edit(new_path)
  vim.cmd("normal! G")
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneBranch", function()
    M.create("child")
  end, { desc = "Create the next note one level deeper (1a -> 1a1)" })

  vim.api.nvim_create_user_command("AriadneSibling", function()
    M.create("sibling")
  end, { desc = "Create the next note at the same level (1a -> 1b)" })
end

return M
