-- Near-duplicate note detection, backed by `ariadne-similar --duplicates`
local utils = require("plugins.ariadne.utils")

local M = {}

local sanitize = utils.sanitize

-- Both paths, not just the left one. The strongest duplicate signal this mode
-- has is the same filename in two folders — title similarity exactly 1.00 — and
-- with only the left path shown there is no way to tell where the right-hand
-- note lives before opening it.
local function describe(pair, vault)
  local function rel(path)
    return sanitize(path:gsub("^" .. vim.pesc(vault) .. "/", ""))
  end
  local mark = pair.verdict == "duplicate" and "DUP " or "    "
  return string.format(
    "%s%.4f  t%.2f  %-30s <-> %-30s  %s | %s",
    mark,
    pair.score,
    pair.title,
    sanitize(pair.a),
    sanitize(pair.b),
    rel(pair.a_path),
    rel(pair.b_path)
  )
end

-- Both thresholds and the size of the band the limit hid: without them a short
-- list reads as "the vault is clean" when it only means "-n was small".
local function header_for(decoded)
  local possible = 0
  for _, pair in ipairs(decoded.pairs) do
    if pair.verdict ~= "duplicate" then
      possible = possible + 1
    end
  end
  return string.format(
    "%d notes -- cosine >= %.2f, titles >= %.2f to call it a duplicate; showing %d of %d possible",
    decoded.scanned or 0,
    decoded.embed_min or 0,
    decoded.title_min or 0,
    possible,
    decoded.possible_total or possible
  )
end

-- Rows name two notes, so selecting one has to pick a side. Enter opens the
-- left-hand note and ctrl-o the right; ctrl-v opens both, which is where a
-- merge starts.
--
-- Each row carries a hidden ordinal and is looked up by it, never by its own
-- text. `utils.sanitize` maps every unprintable byte to a space, so two notes
-- whose names differ only in control characters render identically — keying on
-- the rendered row would let one silently shadow the other and open the wrong
-- note. `--with-nth` hides field 1 from display and from matching; fzf still
-- returns the original line, ordinal included.
local function open_picker(decoded, vault)
  local lines = {}
  local pair_by_index = {}
  for i, pair in ipairs(decoded.pairs) do
    table.insert(lines, i .. "\t" .. describe(pair, vault))
    pair_by_index[i] = pair
  end

  local function selected_pair(selected)
    if not selected or #selected == 0 then
      return nil
    end
    return pair_by_index[tonumber(selected[1]:match("^(%d+)\t"))]
  end

  local function opener(side)
    return function(selected)
      local pair = selected_pair(selected)
      if pair then
        utils.edit(pair[side])
      end
    end
  end

  require("fzf-lua").fzf_exec(lines, {
    prompt = "Duplicates> ",
    fzf_opts = {
      ["--header"] = header_for(decoded),
      ["--delimiter"] = "\t",
      ["--with-nth"] = "2..",
    },
    actions = {
      ["default"] = opener("a_path"),
      ["ctrl-o"] = opener("b_path"),
      ["ctrl-v"] = function(selected)
        local pair = selected_pair(selected)
        if not pair then
          return
        end
        -- Only split once the left note is actually open, or the split shows
        -- whatever buffer happened to be current beside an unrelated note.
        -- `rightbelow` so the layout matches the row regardless of `splitright`.
        if utils.edit(pair.a_path) then
          vim.cmd("rightbelow vsplit")
          utils.edit(pair.b_path)
        end
      end,
    },
  })
end

local function handle(result, vault)
  local output = result.stdout or ""
  local ok, decoded = pcall(vim.json.decode, output)
  if not ok or type(decoded) ~= "table" or type(decoded.pairs) ~= "table" then
    local stderr = result.stderr or ""
    local detail = output ~= "" and output:sub(1, 200)
      or (stderr ~= "" and stderr:sub(1, 200))
      or ("exit code " .. tostring(result.code))
    vim.notify("ariadne-similar --duplicates failed: " .. sanitize(detail), vim.log.levels.ERROR)
    return
  end

  if not decoded.available then
    vim.notify("ariadne-similar: " .. sanitize(decoded.error or "embeddings unavailable"), vim.log.levels.WARN)
    return
  end
  if result.stderr and result.stderr ~= "" then
    vim.notify("ariadne-similar: " .. sanitize(vim.trim(result.stderr)), vim.log.levels.INFO)
  end
  if #decoded.pairs == 0 then
    vim.notify("No duplicate or near-duplicate notes found", vim.log.levels.INFO)
    return
  end
  open_picker(decoded, vault)
end

function M.find_duplicates(limit)
  if vim.fn.executable("ariadne-similar") == 0 then
    vim.notify("ariadne-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR)
    return
  end

  local vault = utils.vault_path
  local argv = { "ariadne-similar", "--duplicates", vault, "--json" }
  if limit and limit ~= "" then
    -- Checked here rather than left to argparse, whose usage dump reaches the
    -- user as an opaque one-line "failed:" notification.
    local n = tonumber(limit)
    if not n or n < 1 or n % 1 ~= 0 then
      vim.notify("AriadneDuplicates: limit must be a positive integer, got " .. sanitize(limit), vim.log.levels.ERROR)
      return
    end
    vim.list_extend(argv, { "-n", tostring(math.floor(n)) })
  end

  -- Async, and not only for the embedding round trip this shares with
  -- :AriadneSimilar: the scan itself compares every pair of notes, which is
  -- 48s at 3040 notes, and a warm cache does not shorten it.
  vim.notify("Scanning " .. vault .. " for duplicates...", vim.log.levels.INFO)
  vim.system(argv, { text = true }, function(result)
    vim.schedule(function()
      handle(result, vault)
    end)
  end)
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneDuplicates", function(cmd)
    M.find_duplicates(cmd.args)
  end, { nargs = "?", desc = "Find duplicate and near-duplicate notes (optional: limit for the 'possible' band)" })
end

return M
