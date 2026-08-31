-- Orphan / sparsely-connected note detection, backed by the `notes-graph` CLI tool
local utils = require("plugins.obsidian.utils")

local M = {}

local function run_notes_graph()
  if vim.fn.executable("notes-graph") == 0 then
    vim.notify("notes-graph not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return nil
  end

  local result = vim.system({ "notes-graph", utils.vault_path, "--json" }, { text = true }):wait()
  local output = result.stdout or ""
  if result.stderr and result.stderr ~= "" then
    vim.notify("notes-graph: " .. result.stderr, vim.log.levels.WARN)
  end

  local ok, decoded = pcall(vim.json.decode, output)
  if not ok or type(decoded) ~= "table" or type(decoded.orphans) ~= "table" or type(decoded.sparse) ~= "table" then
    local detail = output == "" and "(no output)" or output:sub(1, 200)
    vim.notify("Failed to parse notes-graph output: " .. detail, vim.log.levels.ERROR)
    return nil
  end
  return decoded
end

local function describe(entry, vault)
  local plural = entry.degree == 1 and "link" or "links"
  local status = entry.degree == 0 and "ORPHAN" or "SPARSE"
  local rel = entry.path:gsub("^" .. vim.pesc(vault) .. "/", "")
  return string.format("[%s] %-30s (%d %s)  %s", status, entry.name, entry.degree, plural, rel)
end

function M.check_health()
  local result = run_notes_graph()
  if not result then
    return
  end

  local entries = {}
  vim.list_extend(entries, result.orphans)
  vim.list_extend(entries, result.sparse)
  if #entries == 0 then
    vim.notify("No orphaned or sparsely-connected notes found", vim.log.levels.INFO)
    return
  end

  local lines = {}
  local path_by_line = {}
  for _, entry in ipairs(entries) do
    local line = describe(entry, utils.vault_path)
    table.insert(lines, line)
    path_by_line[line] = entry.path
  end

  require("fzf-lua").fzf_exec(lines, {
    prompt = "Graph health> ",
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
  end, { desc = "Find orphan and sparsely-connected notes" })
end

return M
