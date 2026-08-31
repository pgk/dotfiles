-- Orphan, sparse and hubless-cluster detection, backed by the `notes-graph` CLI tool
local utils = require("plugins.obsidian.utils")

local M = {}

-- Note names and paths come from note content, not from nvim itself; strip
-- control chars so a crafted note can't split one entry into several picker rows
-- with mismatched path_by_line keys. Same reason as similar.lua.
local function sanitize(s)
  return (tostring(s or ""):gsub("%c", " "))
end

local function run_notes_graph()
  if vim.fn.executable("notes-graph") == 0 then
    vim.notify("notes-graph not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return nil
  end

  local result = vim.system({ "notes-graph", utils.vault_path, "--json" }, { text = true }):wait()
  local output = result.stdout or ""
  if result.stderr and result.stderr ~= "" then
    vim.notify("notes-graph: " .. sanitize(result.stderr), vim.log.levels.WARN)
  end

  local ok, decoded = pcall(vim.json.decode, output)
  if not ok or type(decoded) ~= "table" or type(decoded.orphans) ~= "table" or type(decoded.sparse) ~= "table" then
    local detail = output == "" and "(no output)" or output:sub(1, 200)
    vim.notify("Failed to parse notes-graph output: " .. sanitize(detail), vim.log.levels.ERROR)
    return nil
  end
  return decoded
end

local function describe(entry, vault)
  local plural = entry.degree == 1 and "link" or "links"
  local status = entry.degree == 0 and "ORPHAN" or "SPARSE"
  local rel = sanitize(entry.path:gsub("^" .. vim.pesc(vault) .. "/", ""))
  return string.format("[%s] %-30s (%d %s)  %s", status, sanitize(entry.name), entry.degree, plural, rel)
end

-- A cluster row names the note that comes closest to being its entry point, since
-- that is what you would promote to a map of content -- or write next to.
local function describe_cluster(entry)
  return string.format(
    "[NO HUB] %-30s (%d notes, best reaches %d of %d)  %s",
    sanitize(entry.name),
    entry.size,
    entry.reach,
    entry.others,
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
    shape.notes or 0,
    shape.edges or 0,
    shape.components or 0,
    shape.largest_component or 0,
    shape.clusters or 0,
    shape.modularity or 0
  )
end

function M.check_health()
  local result = run_notes_graph()
  if not result then
    return
  end

  local lines = {}
  local path_by_line = {}
  -- Hubless clusters first: there are a handful of them at most, and hundreds of
  -- sparse notes would otherwise bury them.
  for _, entry in ipairs(result.hubless_clusters or {}) do
    local line = describe_cluster(entry)
    table.insert(lines, line)
    path_by_line[line] = entry.entry_point
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
    vim.notify("No orphaned or sparsely-connected notes, and every cluster has a hub", vim.log.levels.INFO)
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
        local path = path_by_line[selected[1]]
        if path then
          vim.cmd("edit " .. vim.fn.fnameescape(path))
        end
      end,
    },
  })
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianGraphHealth", function()
    M.check_health()
  end, { desc = "Find orphan and sparsely-connected notes, and clusters with no hub" })
end

return M
