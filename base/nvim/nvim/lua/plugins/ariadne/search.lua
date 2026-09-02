-- Free-text semantic search over the vault, grouped by cluster, backed by
-- `ariadne-similar --search`
local utils = require("plugins.ariadne.utils")
local cli = require("plugins.ariadne.cli")

local M = {}

local sanitize = utils.sanitize

local function describe(hit, vault)
  local cluster = type(hit.cluster) == "number" and ("cluster " .. hit.cluster) or "no cluster"
  return string.format("[%s]  %.4f  %-38s  %s", cluster, hit.score, sanitize(hit.name), cli.relative(hit.path, vault))
end

local function header_for(decoded)
  local hits = 0
  for _, group in ipairs(decoded.groups) do
    hits = hits + #group.hits
  end
  local header = string.format(
    "%d notes -- %d hit(s) across %d cluster(s) for '%s'",
    cli.num(decoded.total_notes),
    hits,
    #decoded.groups,
    sanitize(decoded.query or "")
  )
  local shape = cli.header_for(decoded.shape)
  return shape and (header .. " -- " .. shape) or header
end

-- Ordinal-keyed, like duplicates.lua: two hits that render identically (a
-- sanitized control character colliding with its own escape sequence, say)
-- would otherwise let one silently shadow the other in a text-keyed map.
local function open_picker(decoded, vault)
  local lines = {}
  local path_by_index = {}
  local i = 0
  for _, group in ipairs(decoded.groups) do
    for _, hit in ipairs(group.hits) do
      i = i + 1
      table.insert(lines, i .. "\t" .. describe(hit, vault))
      path_by_index[i] = hit.path
    end
  end

  require("fzf-lua").fzf_exec(lines, {
    prompt = "Search> ",
    fzf_opts = {
      ["--header"] = header_for(decoded),
      ["--delimiter"] = "\t",
      ["--with-nth"] = "2..",
    },
    actions = {
      ["default"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        local path = path_by_index[tonumber(selected[1]:match("^(%d+)\t"))]
        if path then
          utils.edit(path)
        end
      end,
    },
  })
end

local function handle(result, vault)
  local decoded = cli.decode("ariadne-similar --search", result, "groups")
  if not decoded then
    return
  end
  if #decoded.groups == 0 then
    vim.notify("No matches found", vim.log.levels.INFO)
    return
  end
  open_picker(decoded, vault)
end

function M.search(phrase)
  -- Checked here rather than left to the CLI, whose refusal reaches the user
  -- as an opaque one-line "failed:" notification (same reasoning as
  -- duplicates.lua's client-side limit check).
  if phrase == nil or vim.trim(phrase) == "" then
    return
  end
  if vim.fn.executable("ariadne-similar") == 0 then
    vim.notify("ariadne-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end

  local vault = utils.vault_path
  -- Async, matching similar.lua/duplicates.lua: a search embeds the phrase
  -- plus any unindexed notes over HTTP, which can outlast any wait budget
  -- worth freezing the editor for.
  vim.system({ "ariadne-similar", "--search", phrase, vault, "--json" }, { text = true }, function(result)
    vim.schedule(function()
      handle(result, vault)
    end)
  end)
end

function M.prompt()
  M.search(vim.fn.input("Semantic search: "))
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneSearch", function(cmd)
    if cmd.args ~= "" then
      M.search(cmd.args)
    else
      M.prompt()
    end
  end, { nargs = "?", desc = "Semantic search by phrase, grouped by cluster" })
end

return M
