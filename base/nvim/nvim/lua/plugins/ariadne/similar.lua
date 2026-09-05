-- Semantically similar but unlinked note detection, backed by the `ariadne-similar` CLI tool
local utils = require("plugins.ariadne.utils")
local cli = require("plugins.ariadne.cli")
local selection = require("plugins.ariadne.selection")

local M = {}

local sanitize = utils.sanitize

local function describe(entry, vault)
  local rel = cli.relative(entry.path, vault)
  local label = sanitize(entry.name)
    .. (entry.linked and " [linked]" or "")
    .. (entry.crosses and type(entry.cluster) == "number" and (" [cluster " .. entry.cluster .. "]") or "")
  return string.format("%.4f  %-38s %-40s %s", entry.score, label, sanitize(entry.preview), rel)
end

local function open_picker(result, vault, origin, opts)
  local lines = {}
  local path_by_line = {}
  local name_by_line = {}
  for _, entry in ipairs(result.similar) do
    local line = describe(entry, vault)
    table.insert(lines, line)
    path_by_line[line] = entry.path
    name_by_line[line] = sanitize(entry.name)
  end

  local header = cli.header_for(result.shape)
  if result.passage and result.passage ~= vim.NIL then
    -- Which paragraph this answers is the one thing the rows cannot show, and
    -- a selection is easy to lose track of while an async query runs.
    -- Collapse first, sanitize second: sanitize escapes control characters, so
    -- doing it first turns every newline in a multi-line selection into a
    -- literal `<0A>` that `%s+` can no longer collapse. The extra parens keep
    -- gsub's replacement count out of the argument list. Escaping still happens
    -- for what matters -- `%s` covers only whitespace, so an ESC or a bidi mark
    -- still reaches sanitize.
    local passage = sanitize((vim.trim(result.passage):gsub("%s+", " ")))
    -- Character-wise, not byte-wise: `:sub` would cut a multi-byte character in
    -- half and put invalid UTF-8 in the header.
    if vim.fn.strchars(passage) > 60 then
      passage = vim.fn.strcharpart(passage, 0, 57) .. "..."
    end
    header = header and ("passage: " .. passage .. " -- " .. header) or ("passage: " .. passage)
  end
  require("fzf-lua").fzf_exec(lines, {
    prompt = opts.prompt,
    fzf_opts = header and { ["--header"] = header } or nil,
    actions = {
      ["default"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        utils.edit(path_by_line[selected[1]])
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

local function handle(result, vault, origin, opts)
  local decoded = cli.decode("ariadne-similar", result, "similar")
  if not decoded then
    return
  end
  if #decoded.similar == 0 then
    vim.notify(opts.empty, vim.log.levels.INFO)
    return
  end
  open_picker(decoded, vault, origin, opts)
end

-- Both queries are the same round trip -- async, `similar`-shaped JSON, the
-- same picker -- and differ only in argv and in what an empty result means.
-- Async rather than :wait(): a query may embed up to --max-refresh notes over
-- HTTP, which can outlast any wait budget worth freezing the editor for.
local function query(argv, vault, opts)
  if vim.fn.executable("ariadne-similar") == 0 then
    vim.notify("ariadne-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end
  -- Captured before the query, not inside the callback: ctrl-y writes a wikilink
  -- back into the note the query started from.
  local origin = { win = vim.api.nvim_get_current_win(), buf = vim.api.nvim_get_current_buf() }
  vim.system(argv, { text = true }, function(result)
    vim.schedule(function()
      handle(result, vault, origin, opts)
    end)
  end)
end

function M.find_similar()
  local current = vim.api.nvim_buf_get_name(0)
  local vault = utils.vault_path

  if not utils.in_vault(current) then
    vim.notify("Current buffer is not a note in " .. vault, vim.log.levels.WARN)
    return
  end
  query({ "ariadne-similar", current, vault, "--json" }, vault, {
    prompt = "Similar> ",
    empty = "No unlinked similar notes found",
  })
end

-- The visual selection as the query, instead of the whole note. `--from` names
-- the note it came from, which is what keeps that note out of its own results
-- and makes the ranking crossing-vs-within rather than grouped by cluster.
function M.search_selection()
  local current = vim.api.nvim_buf_get_name(0)
  local vault = utils.vault_path

  if not utils.in_vault(current) then
    vim.notify("Current buffer is not a note in " .. vault, vim.log.levels.WARN)
    return
  end
  local text = selection.visual_selection()
  if not text or vim.trim(text) == "" then
    vim.notify("No text selected", vim.log.levels.WARN)
    return
  end
  -- `--search=TEXT`, not `--search TEXT`: argparse reads any bare token starting
  -- with `-` as an option, so selecting a `---` rule -- or a lone flag out of a
  -- code block -- aborted the whole command with a usage dump. The `=` form is
  -- split on the first `=` and never re-inspected.
  query({ "ariadne-similar", "--search=" .. text, "--from", current, vault, "--json" }, vault, {
    prompt = "Passage> ",
    empty = "No unlinked notes similar to that passage",
  })
end

function M.reindex(opts)
  if vim.fn.executable("ariadne-similar") == 0 then
    vim.notify("ariadne-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end

  local vault = utils.vault_path
  local argv = { "ariadne-similar", "--index", vault }
  if opts and opts.rebuild then
    table.insert(argv, "--rebuild")
  end

  vim.notify("Rebuilding the ariadne-similar index for " .. vault .. "...", vim.log.levels.INFO)
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
  vim.api.nvim_create_user_command("AriadneSimilar", function()
    M.find_similar()
  end, { desc = "Find semantically similar but unlinked notes" })

  -- range = true so the command is reachable as :'<,'>AriadneSearchSelection;
  -- the range itself is unused, since the '< / '> marks carry the columns a
  -- line range would have thrown away.
  vim.api.nvim_create_user_command("AriadneSearchSelection", function()
    M.search_selection()
  end, { range = true, desc = "Find notes similar to the selected passage" })

  vim.api.nvim_create_user_command("AriadneSimilarIndex", function(cmd)
    M.reindex({ rebuild = cmd.bang })
  end, { bang = true, desc = "Refresh the ariadne-similar embedding index (! to rebuild from scratch)" })
end

return M
