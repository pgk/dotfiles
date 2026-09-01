-- Recent-activity overview, backed by `notes-graph --since`
local utils = require("plugins.obsidian.utils")

local M = {}

local sanitize = utils.sanitize

local function num(v)
  return type(v) == "number" and v or 0
end

local function run_notes_graph(window)
  return utils.run_notes_tool("notes-graph", { "--since", window }, { "active_clusters" })
end

local function describe(entry, tag)
  local plural = num(entry.degree) == 1 and "link" or "links"
  return string.format(
    "%-12s %-34s (%d %s, %s)  %s",
    tag,
    sanitize(entry.name),
    num(entry.degree),
    plural,
    sanitize(entry.age),
    sanitize(entry.rel)
  )
end

function M.show(window)
  window = window and window ~= "" and window or "7d"
  local result = run_notes_graph(window)
  if not result then
    return
  end

  local lines = {}
  local path_by_line = {}
  local function add(entry, tag)
    local line = describe(entry, tag)
    table.insert(lines, line)
    path_by_line[line] = entry.path
  end

  -- Clusters first, in the order notes-graph ranked them: most-touched first, which
  -- is the "what was I working on" answer. The cluster tag repeats on every row so
  -- the grouping survives fzf's filtering.
  for _, cluster in ipairs(result.active_clusters) do
    local tag = string.format("[c%d %d/%d]", num(cluster.cluster), num(cluster.touched), num(cluster.size))
    for _, entry in ipairs(cluster.notes or {}) do
      add(entry, tag)
    end
  end
  for _, entry in ipairs(result.touched_orphans or {}) do
    add(entry, "[ORPHANED]")
  end

  if #lines == 0 then
    vim.notify("Nothing touched in the last " .. window, vim.log.levels.INFO)
    return
  end

  local header = string.format(
    "%d of %d notes touched in the last %s",
    num(result.touched),
    num(result.total_notes),
    window
  )
  require("fzf-lua").fzf_exec(lines, {
    prompt = "Active> ",
    fzf_opts = { ["--header"] = header },
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
  vim.api.nvim_create_user_command("ObsidianActive", function(opts)
    M.show(opts.args)
  end, { nargs = "?", desc = "Notes touched recently, grouped by cluster (default: 7d)" })
end

return M
