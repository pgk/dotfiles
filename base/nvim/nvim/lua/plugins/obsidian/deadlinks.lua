-- Dead wikilink detection with fuzzy match suggestions, backed by the `notes-deadlinks` CLI tool
local utils = require("plugins.obsidian.utils")

local M = {}

local function run_notes_deadlinks()
  return utils.run_notes_tool("notes-deadlinks", {}, { "notes_with_dead_links" })
end

local sanitize = utils.sanitize

local function describe(note, dead_link, vault)
  local rel = sanitize(note.path:gsub("^" .. vim.pesc(vault) .. "/", ""))
  local suffix = #dead_link.candidates > 0 and ("possible: " .. table.concat(dead_link.candidates, ", ")) or "no matches"
  return string.format(
    "%-30s [[%s]]  %s  %s",
    sanitize(note.name),
    sanitize(dead_link.link),
    sanitize(suffix),
    rel
  )
end

function M.check_dead_links()
  local result = run_notes_deadlinks()
  if not result then
    return
  end

  local lines = {}
  local path_by_line = {}
  for _, note in ipairs(result.notes_with_dead_links) do
    for _, dead_link in ipairs(note.dead_links) do
      local line = describe(note, dead_link, utils.vault_path)
      table.insert(lines, line)
      path_by_line[line] = note.path
    end
  end

  if #lines == 0 then
    vim.notify("No dead links found", vim.log.levels.INFO)
    return
  end

  require("fzf-lua").fzf_exec(lines, {
    prompt = "Dead links> ",
    actions = {
      ["default"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        utils.edit(path_by_line[selected[1]])
      end,
    },
  })
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianDeadLinks", function()
    M.check_dead_links()
  end, { desc = "Find dead links and possible matches" })
end

return M
