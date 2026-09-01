-- Orphan, sparse, splittable and hubless-cluster detection, backed by the `ariadne-graph` CLI tool
local utils = require("plugins.ariadne.utils")

local M = {}

local sanitize = utils.sanitize

-- Every number below comes from ariadne-graph's own arithmetic, but vim.json.decode
-- maps a JSON null to vim.NIL, which is truthy -- so `x or 0` would pass it
-- straight into string.format and throw.
local function num(v)
  return type(v) == "number" and v or 0
end

local function run_notes_graph()
  return utils.run_ariadne_tool("ariadne-graph", {}, { "orphans", "sparse", "splittable" })
end

local function describe(entry, vault)
  local plural = entry.degree == 1 and "link" or "links"
  local status = entry.degree == 0 and "ORPHAN" or "SPARSE"
  local rel = sanitize(entry.path:gsub("^" .. vim.pesc(vault) .. "/", ""))
  return string.format("[%s] %-30s (%d %s)  %s", status, sanitize(entry.name), entry.degree, plural, rel)
end

-- A cluster row names its best-connected member, since that is what you would
-- promote to a map of content -- or write next to. In a ring every member ties,
-- so treat it as a starting place rather than a recommendation.
local function describe_cluster(entry)
  return string.format(
    "[NO HUB] %-30s (%d notes, best reaches %d of %d)  %s",
    sanitize(entry.name),
    num(entry.size),
    num(entry.reach),
    num(entry.others),
    sanitize(entry.rel)
  )
end

local function describe_splittable(entry)
  local headers = type(entry.headers) == "table" and entry.headers or {}
  local plural = num(entry.out_degree) == 1 and "link" or "links"
  return string.format(
    "[SPLIT] %-30s (%d words, %d sections, %d outbound %s)  %s",
    sanitize(entry.name),
    num(entry.words),
    #headers,
    num(entry.out_degree),
    plural,
    sanitize(entry.rel)
  )
end

-- The clustering is never tuned against the real vault, so the picker shows the
-- graph it ran on: many tiny components, or a modularity near zero, means the
-- [NO HUB] rows are noise.
local function header_for(shape)
  if type(shape) ~= "table" then
    return nil
  end
  return string.format(
    "%d notes, %d links, %d components, largest %d -- %d clusters, modularity %.3f",
    num(shape.notes),
    num(shape.edges),
    num(shape.components),
    num(shape.largest_component),
    num(shape.clusters),
    num(shape.modularity)
  )
end

function M.check_health()
  local result = run_notes_graph()
  if not result then
    return
  end

  local lines = {}
  local path_by_line = {}
  -- Hubless clusters first, largest first: the big ones are the actionable ones,
  -- and hundreds of sparse notes would otherwise bury them.
  local hubless = type(result.hubless_clusters) == "table" and result.hubless_clusters or {}
  for _, entry in ipairs(hubless) do
    local line = describe_cluster(entry)
    table.insert(lines, line)
    path_by_line[line] = entry.entry_point
  end

  -- Splittable notes next: a small, actionable category like hubless clusters,
  -- which the orphan/sparse dump below would otherwise bury.
  local splittable = type(result.splittable) == "table" and result.splittable or {}
  for _, entry in ipairs(splittable) do
    local line = describe_splittable(entry)
    table.insert(lines, line)
    path_by_line[line] = entry.path
  end

  local nodes = {}
  vim.list_extend(nodes, result.orphans)
  vim.list_extend(nodes, result.sparse)
  for _, entry in ipairs(nodes) do
    local line = describe(entry, utils.vault_path)
    table.insert(lines, line)
    path_by_line[line] = entry.path
  end

  if #lines == 0 then
    vim.notify(
      "No orphaned or sparsely-connected notes, every cluster has a hub, and nothing looks like it needs splitting",
      vim.log.levels.INFO
    )
    return
  end

  local header = header_for(result.shape)
  require("fzf-lua").fzf_exec(lines, {
    prompt = "Graph health> ",
    fzf_opts = header and { ["--header"] = header } or nil,
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
  vim.api.nvim_create_user_command("AriadneGraphHealth", function()
    M.check_health()
  end, { desc = "Find orphan/sparse/splittable notes, and clusters with no hub" })
end

return M
