-- Semantically similar but unlinked note detection, backed by the `notes-similar` CLI tool
local utils = require("plugins.obsidian.utils")

local M = {}

-- Note names, previews and paths come from note content, not from nvim itself;
-- strip control chars so a crafted note can't split one entry into several
-- picker rows with mismatched path_by_line keys, and so a name containing a
-- newline can't make nvim_put throw when inserted as a link. Same reason as
-- deadlinks.lua.
local function sanitize(s)
  return (tostring(s or ""):gsub("%c", " "))
end

local function describe(entry, vault)
  local rel = sanitize(entry.path:gsub("^" .. vim.pesc(vault) .. "/", ""))
  local label = sanitize(entry.name)
    .. (entry.linked and " [linked]" or "")
    .. (entry.crosses and type(entry.cluster) == "number" and (" [cluster " .. entry.cluster .. "]") or "")
  return string.format("%.4f  %-38s %-40s %s", entry.score, label, sanitize(entry.preview), rel)
end

-- The clustering is never tuned against the real vault, so the picker shows the
-- graph it ran on: many tiny components, or a modularity near zero, means the
-- [cluster N] marks are noise.
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

local function open_picker(result, vault, origin)
  local lines = {}
  local path_by_line = {}
  local name_by_line = {}
  for _, entry in ipairs(result.similar) do
    local line = describe(entry, vault)
    table.insert(lines, line)
    path_by_line[line] = entry.path
    name_by_line[line] = sanitize(entry.name)
  end

  local header = header_for(result.shape)
  require("fzf-lua").fzf_exec(lines, {
    prompt = "Similar> ",
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
      ["ctrl-y"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        local name = name_by_line[selected[1]]
        if not name then
          vim.notify("Could not resolve the selected note", vim.log.levels.WARN)
          return
        end
        -- The query is async, so the window may be gone or showing a different
        -- buffer by now; inserting into whatever replaced it would be wrong.
        if not vim.api.nvim_win_is_valid(origin.win) then
          vim.notify("The window this picker was opened from is gone", vim.log.levels.WARN)
          return
        end
        if vim.api.nvim_win_get_buf(origin.win) ~= origin.buf then
          vim.notify("That window is no longer showing the note you started from", vim.log.levels.WARN)
          return
        end
        vim.api.nvim_set_current_win(origin.win)
        vim.api.nvim_put({ "[[" .. name .. "]]" }, "c", true, true)
      end,
    },
  })
end

local function handle(result, vault, origin)
  local output = result.stdout or ""
  local ok, decoded = pcall(vim.json.decode, output)
  if not ok or type(decoded) ~= "table" or type(decoded.similar) ~= "table" then
    -- Prefer stderr: a crash exits non-zero with an empty stdout, and "(no output)"
    -- hides the reason. Both streams are CLI-derived, so both get sanitized.
    local detail = output ~= "" and output:sub(1, 200)
      or (result.stderr ~= "" and result.stderr:sub(1, 200))
      or ("exit code " .. tostring(result.code))
    vim.notify("notes-similar failed: " .. sanitize(detail), vim.log.levels.ERROR)
    return
  end

  if not decoded.available then
    -- stderr carries the same reason, so report only the structured one here.
    vim.notify("notes-similar: " .. sanitize(decoded.error or "embeddings unavailable"), vim.log.levels.WARN)
    return
  end
  -- Surfaced only on the success path, where it is not a duplicate of `error`:
  -- carries the "sending N notes to <endpoint>" egress notice and duplicate-name warnings.
  if result.stderr and result.stderr ~= "" then
    vim.notify("notes-similar: " .. sanitize(vim.trim(result.stderr)), vim.log.levels.INFO)
  end
  if #decoded.similar == 0 then
    vim.notify("No unlinked similar notes found", vim.log.levels.INFO)
    return
  end
  open_picker(decoded, vault, origin)
end

function M.find_similar()
  local current = vim.api.nvim_buf_get_name(0)
  local vault = utils.vault_path

  if current == "" or not vim.startswith(current, vault .. "/") then
    vim.notify("Current buffer is not a note in " .. vault, vim.log.levels.WARN)
    return
  end
  if vim.fn.executable("notes-similar") == 0 then
    vim.notify("notes-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end

  local origin = { win = vim.api.nvim_get_current_win(), buf = vim.api.nvim_get_current_buf() }
  -- Async rather than :wait(): a query may embed up to --max-refresh notes over
  -- HTTP, which can outlast any wait budget worth freezing the editor for.
  vim.system({ "notes-similar", current, vault, "--json" }, { text = true }, function(result)
    vim.schedule(function()
      handle(result, vault, origin)
    end)
  end)
end

function M.reindex(opts)
  if vim.fn.executable("notes-similar") == 0 then
    vim.notify("notes-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end

  local vault = utils.vault_path
  local argv = { "notes-similar", "--index", vault }
  if opts and opts.rebuild then
    table.insert(argv, "--rebuild")
  end

  vim.notify("Rebuilding the notes-similar index for " .. vault .. "...", vim.log.levels.INFO)
  vim.system(argv, { text = true }, function(result)
    vim.schedule(function()
      local message = (result.code == 0 and result.stdout or result.stderr) or ""
      vim.notify(
        sanitize(vim.trim(message)),
        result.code == 0 and vim.log.levels.INFO or vim.log.levels.ERROR
      )
    end)
  end)
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianSimilar", function()
    M.find_similar()
  end, { desc = "Find semantically similar but unlinked notes" })

  vim.api.nvim_create_user_command("ObsidianSimilarIndex", function(cmd)
    M.reindex({ rebuild = cmd.bang })
  end, { bang = true, desc = "Refresh the notes-similar embedding index (! to rebuild from scratch)" })
end

return M
