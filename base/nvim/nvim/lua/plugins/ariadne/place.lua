-- Placing a note that has no Folgezettel id into the hierarchy.
--
-- `folgezettel.lua` can say what a child or a sibling of a given id is; nothing
-- in the grammar can say which note *this* one belongs under. That is a
-- retrieval question, so it is answered the way `:AriadneSimilar` answers "what
-- is this note near" -- with `ariadne-similar` -- and then narrowed to the
-- neighbours whose own names parse as an id, since only those name a place.
local branch = require("plugins.ariadne.branch")
local cli = require("plugins.ariadne.cli")
local commands = require("plugins.ariadne.commands")
local folgezettel = require("plugins.ariadne.folgezettel")
local utils = require("plugins.ariadne.utils")

local M = {}

-- Asked of the CLI, then narrowed to the id-bearing neighbours. Wide, because
-- that filter is invisible to the ranking: in a vault where most notes have no
-- id yet -- which is exactly the vault this command is for -- a default ten
-- results can be ten notes that name no place at all.
local CANDIDATE_LIMIT = 50
-- Neighbours turned into rows. Two rows each, so this is half the picker.
local MAX_PARENTS = 8

-- A child elaborates the note it sits under; a sibling continues that note's
-- line. The id grammar cannot tell which one a note is, so both are offered and
-- the wording says which is which rather than leaving it to the id.
local KINDS = {
  { label = "child of", next_id = folgezettel.child, lead = "Branched from" },
  -- A sibling continues the line it joins; it did not branch off the note before
  -- it. Same distinction, and same wording, as `branch.lua`.
  { label = "sibling of", next_id = folgezettel.sibling, lead = "Continues" },
}

-- One row per (neighbour, kind), in the order the ranking returned, plus a
-- final row for a note that belongs under nothing.
--
-- Deduplicated by the id being proposed, and that is not cosmetic: `sibling of
-- 1a1` and `sibling of 1a2` both walk to the first free id in the 1a line, so
-- without it the picker offers one slot twice and the losing row names a parent
-- the result would not sit next to.
local function placements(entries, taken)
  -- `matched` counts every id-bearing neighbour, `parents` only the ones turned
  -- into rows. Separate counters because the header reports how thin the
  -- evidence is, and reusing the capped one understated it exactly when the
  -- evidence was richest -- ten id-bearing neighbours reported as eight.
  local rows, seen, parents, matched = {}, {}, 0, 0
  local function add(row)
    local key = row.id:lower()
    if not seen[key] then
      seen[key] = true
      table.insert(rows, row)
    end
  end
  for _, entry in ipairs(entries) do
    -- `cli.decode` only establishes that `similar` is a table. Everything below
    -- indexes into its elements and two of those values reach the filesystem, so
    -- the shape is checked here rather than thrown inside a scheduled callback.
    local id = type(entry) == "table"
      and type(entry.name) == "string"
      and type(entry.path) == "string"
      and folgezettel.split(entry.name)
    if id then
      matched = matched + 1
      if parents < MAX_PARENTS then
        parents = parents + 1
        for _, kind in ipairs(KINDS) do
          add({
            id = folgezettel.first_free(kind.next_id(id), taken),
            kind = kind.label,
            lead = kind.lead,
            entry = entry,
          })
        end
      end
    end
  end
  -- Always offered, and last: a note nothing in the vault is a parent for still
  -- has a place, at the top level. It is also the only row an empty result can
  -- show, which is better than a picker with nothing in it.
  add({ id = folgezettel.first_free("1", taken), kind = "new top-level sequence" })
  return rows, matched
end

local function describe(row, vault)
  if not row.entry then
    -- A dashed score cell rather than blank: fzf-lua hands a row back as the
    -- string it rendered, and a row that starts with the padding of a column it
    -- has no value for does not line up with the rest under a fixed format.
    return string.format("%-6s  %-8s %s", "------", row.id, row.kind)
  end
  local label = utils.sanitize(row.entry.name) .. (row.entry.linked and " [linked]" or "")
  -- Clamped, because `%-40s` pads but never truncates and `sanitize` leaves runs
  -- of ordinary spaces alone: a note name padded with spaces would otherwise
  -- push the parent's path out of the readable part of the row, and the row is
  -- what tells the user which directory their note is about to move into.
  -- Character-wise, or a multi-byte name gets cut in half.
  label = vim.fn.strcharpart(label, 0, 40)
  return string.format(
    "%.4f  %-8s %-11s %-40s %s",
    cli.num(row.entry.score),
    row.id,
    row.kind,
    label,
    cli.relative(row.entry.path, vault)
  )
end

-- The id implies the relationship; `ariadne-graph` counts wikilinks. A placed
-- note with no edge to its parent is an orphan by that measure -- the invariant
-- `branch.lua` writes its `Branched from` line for, and it applies to a note
-- placed into the sequence exactly as it does to one created in it.
--
-- Conditional, unlike branch.lua's, because a note being placed is not new: it
-- may already reference its parent, and the ranking already told us so. `linked`
-- covers either direction, so a parent linking *to* the note counts too -- the
-- edge exists and a second one adds nothing. Runs after the rename, so the
-- buffer is already the renamed note.
local function link_to_parent(row)
  if not row.entry or row.entry.linked then
    return
  end
  vim.api.nvim_buf_set_lines(0, 0, 0, false, { row.lead .. " " .. utils.as_wikilink(row.entry.name), "" })
  -- No path argument: this writes the buffer to the file it already names.
  local ok, err = pcall(vim.cmd.write)
  if not ok then
    vim.notify("Placed, but could not write the parent link: " .. utils.sanitize(err), vim.log.levels.WARN)
  end
end

-- Rename into the chosen slot.
--
-- The query is async, so by the time a row is picked the window may be gone or
-- showing something else -- and `commands.rename` acts on the *current* buffer,
-- which would then be the wrong note. Same hazard `similar.lua`'s ctrl-y guards
-- against, with more at stake: that one inserts a line, this one moves a file
-- and rewrites every link pointing at it.
local function apply(row, origin)
  if not vim.api.nvim_win_is_valid(origin.win) then
    vim.notify("The window this placement was started from is gone", vim.log.levels.WARN)
    return
  end
  if vim.api.nvim_win_get_buf(origin.win) ~= origin.buf then
    vim.notify("That window is no longer showing the note you started from", vim.log.levels.WARN)
    return
  end
  -- The buffer *handle* is not the note. `:saveas` and `:file` rename a buffer
  -- while keeping its handle, so the two checks above both pass and rename then
  -- destroys a different file than the one the ranking, the id and the title
  -- prefill all describe. Compare the name, not the handle.
  --
  -- This subsumes "the note gained an id while the picker was open", which is
  -- why there is no separate check for it: gaining one means being renamed, and
  -- a name that is still `origin.path` has the stem `refusal` already cleared.
  local live = utils.resolve(vim.api.nvim_buf_get_name(origin.buf))
  if live ~= origin.path then
    vim.notify("That buffer is no longer " .. utils.sanitize(origin.title), vim.log.levels.WARN)
    return
  end
  vim.api.nvim_set_current_win(origin.win)

  -- Sanitized, and this is the one prefill that matters: the note's own stem is
  -- attacker-controlled under this threat model, the prompt invites accepting it
  -- with a bare Enter, and what it becomes is a filename. A bidi mark would let
  -- the cmdline render a name other than the bytes about to be written.
  local title = vim.trim(vim.fn.input(row.id .. " ", utils.sanitize(origin.title)))
  if title == "" then
    vim.notify("Cancelled", vim.log.levels.INFO)
    return
  end
  -- Beside the parent, not wherever the note happened to be sitting: a placed
  -- note joins the sequence it was placed in, the rule `branch.lua` already
  -- follows for a note it creates. The top-level row has no parent to join, so
  -- it renames in place.
  local dir = nil
  if row.entry then
    -- `utils.vault_child` contains a name within its base and deliberately does
    -- not check the base itself -- its docstring makes that the caller's job, and
    -- `branch.lua` discharges it from a path already through `in_vault`. Here the
    -- base comes out of the CLI's JSON, so it is checked here. The shipped CLI
    -- cannot emit a path outside the vault (`ariadne_common.iter_markdown_files`
    -- realpath-checks every note it yields), but that is a property of another
    -- process, and what rests on it is a write followed by deleting the original.
    if not utils.in_vault(row.entry.path) then
      vim.notify("That placement names a note outside " .. utils.vault_path, vim.log.levels.WARN)
      return
    end
    dir = vim.fn.fnamemodify(row.entry.path, ":h")
  end
  if not commands.rename(row.id .. " " .. title, { dir = dir }) then
    return
  end
  link_to_parent(row)
end

local function open_picker(rows, parents, total, vault, origin)
  local lines, row_by_line = {}, {}
  for _, row in ipairs(rows) do
    local line = describe(row, vault)
    table.insert(lines, line)
    row_by_line[line] = row
  end
  local header = string.format(
    "placing %s -- %d of the %d nearest notes carry an id",
    utils.sanitize(origin.title),
    parents,
    total
  )
  require("fzf-lua").fzf_exec(lines, {
    prompt = "Place> ",
    fzf_opts = { ["--header"] = header },
    actions = {
      ["default"] = function(selected)
        if not selected or #selected == 0 then
          return
        end
        local row = row_by_line[selected[1]]
        if not row then
          vim.notify("Could not resolve the selected placement", vim.log.levels.WARN)
          return
        end
        apply(row, origin)
      end,
    },
  })
end

local function handle(result, vault, origin)
  local decoded = cli.decode("ariadne-similar", result, "similar")
  if not decoded then
    return
  end
  -- Read after the round trip rather than before it, which is as fresh as this
  -- gets -- not a guarantee. The picker and the blocking title prompt are a
  -- longer window still, and it is left open deliberately; see the Folgezettel
  -- section of CLAUDE.md for why.
  local rows, parents = placements(decoded.similar, branch.taken_ids())
  open_picker(rows, parents, #decoded.similar, vault, origin)
end

-- Why `path` cannot be placed -- message and severity -- or nil if it can. A
-- note that already sits in the hierarchy is the interesting refusal:
-- :AriadneBranch and :AriadneSibling continue from one, so there is nothing for
-- this command to work out.
local function refusal(path, stem)
  if not utils.in_vault(path) or not path:match("%.md$") then
    return "Not a note in " .. utils.vault_path
  end
  local existing = folgezettel.split(stem)
  if existing then
    return utils.sanitize(stem) .. " already has a Folgezettel id (" .. existing .. ")"
  end
  if vim.fn.executable("ariadne-similar") == 0 then
    -- An error rather than a warning, unlike the two above: those are this note
    -- being the wrong note to ask about, this is the command not working at all.
    return "ariadne-similar not found on PATH (see dotfiles/bin)", vim.log.levels.ERROR
  end
  return nil
end

function M.find_placement()
  local path = utils.resolve(vim.api.nvim_buf_get_name(0))
  local vault = utils.vault_path
  local stem = utils.get_note_name(path)
  local why, level = refusal(path, stem)
  if why then
    vim.notify(why, level or vim.log.levels.WARN)
    return
  end

  if vim.bo.modified then
    -- The CLI reads the note off disk, so the ranking answers the saved version.
    -- Said out loud rather than writing the buffer: this command already renames
    -- a file and rewrites links, and a silent write is one more thing it did not
    -- announce.
    vim.notify("Unsaved changes: the placement is ranked against the note on disk", vim.log.levels.WARN)
  end

  -- `--all --no-bridge`, which is not what :AriadneSimilar sends, for two
  -- reasons. Bridge-first ordering promotes the structurally novel pair, and a
  -- parent should be the *nearest* note, not the most surprising one. And a note
  -- already linked to its natural parent is the common case here, not one to
  -- filter out -- it is marked `[linked]` in the row instead.
  local origin = {
    win = vim.api.nvim_get_current_win(),
    buf = vim.api.nvim_get_current_buf(),
    path = path,
    title = stem,
  }
  local argv = {
    "ariadne-similar",
    path,
    vault,
    "--all",
    "--no-bridge",
    "-n",
    tostring(CANDIDATE_LIMIT),
    "--json",
  }
  vim.system(argv, { text = true }, function(result)
    vim.schedule(function()
      handle(result, vault, origin)
    end)
  end)
end

function M.setup()
  vim.api.nvim_create_user_command("AriadnePlace", function()
    M.find_placement()
  end, { desc = "Place an id-less note in the Folgezettel hierarchy, then rename it" })
end

return M
