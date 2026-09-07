-- What links here, written into the note itself.
--
-- `:AriadneBacklinks` keeps a managed block at the end of the current note
-- listing every note that links to it, so the inbound edges are readable in the
-- file and in Obsidian rather than only in the links panel.
--
-- **The block is derived text, not written text.** Every reader here strips it
-- first, and `ariadne_common.strip_backlinks_block` does the same on the Python
-- side. Without that rule it mirrors itself: A links to B, so B's block names A,
-- so A's block names B -- and each note's block fills up with the notes it links
-- to. The vault graph is unaffected either way (`adjacency_from_links` records
-- both directions, so a backlink is already an edge); what the strip protects is
-- everything reading a note *directionally* or as prose.
local utils = require("plugins.ariadne.utils")
local wikilinks = require("plugins.ariadne.wikilinks")

local M = {}

M.OPEN = "<!-- ariadne:backlinks -->"
M.CLOSE = "<!-- /ariadne:backlinks -->"
-- Inside the markers, not above them: `ariadne_splittable` counts a note's `##`
-- headings, and one in every note would drag notes toward its split gate.
M.HEADING = "## Backlinks"

-- Any bullet, for stripping the marker off a line...
local ROW = "^%s*[-*+]%s+"
-- ...but only an unindented one opens a row. An indented bullet is a sub-list
-- under a row -- the most natural way to annotate one -- and promoting it to a
-- row deleted it and reported it as a removed backlink.
local ROW_START = "^[-*+]%s+"
local NAMED = 3

-- Lines inside a closed ``` fence. A note documenting this feature quotes the
-- markers, and a quoted *complete* block was taken as the live one: `:AriadneBacklinks`
-- rewrote the example with real rows and called the example's note a removed
-- backlink. `ariadne_common._fenced_lines` is the same walk. An unterminated
-- fence is not a fence -- the stance `ariadne_common.FENCE_RE` already takes --
-- so a stray ``` cannot hide the rest of a note's markers.
local function fenced(lines)
  local ticks = {}
  for i, line in ipairs(lines) do
    if vim.startswith(vim.trim(line), "```") then
      table.insert(ticks, i)
    end
  end
  local inside = {}
  for i = 1, #ticks - 1, 2 do
    for j = ticks[i], ticks[i + 1] do
      inside[j] = true
    end
  end
  return inside
end

-- Every managed block, as {first, last} line pairs. A block is a line that is
-- exactly the opening marker, a body containing no further opening marker, and a
-- line that is exactly the closing marker. `ariadne_common._block_spans` is the
-- same walk in Python, deliberately line for line: the two are the two answers to
-- "which links did the user write?", and a grammar they disagree on is a mirror
-- on one side and not the other. `backlinks-block.fixture` pins them together.
--
-- The no-nested-opener half is load-bearing rather than tidiness. Pairing the
-- *first* opener with the *first* closer meant an unpaired marker higher up the
-- note -- a hand-pruned block, or a note quoting the markers while documenting
-- them -- swallowed everything down to the real block's closer: the first run
-- appended a block, which supplied the stray marker's missing closer, and the
-- second replaced the whole span, deleting the prose between and reporting
-- "unchanged", since the rows had not moved. An unterminated marker is left
-- alone, as `strip_frontmatter` leaves an unterminated `---`.
function M.spans(lines)
  local found, open = {}, nil
  local inside = fenced(lines)
  for i, line in ipairs(lines) do
    local trimmed = inside[i] and "" or vim.trim(line)
    if trimmed == M.OPEN then
      open = i
    elseif trimmed == M.CLOSE and open then
      table.insert(found, { open, i })
      open = nil
    end
  end
  return found
end

-- The block `update` maintains: the last, since that is where it writes one.
function M.span(lines)
  local found = M.spans(lines)
  local last = found[#found]
  if not last then
    return nil
  end
  return last[1], last[2]
end

-- The note without any of its blocks: what every reader of a note's links wants.
-- Every one, not just the last -- a note that has ended up with two would
-- otherwise have the other read back as authored links, which is the mirror.
function M.strip(text)
  local lines = vim.split(text, "\n", { plain = true })
  local found = M.spans(lines)
  if #found == 0 then
    return text
  end
  local drop = {}
  for _, block in ipairs(found) do
    for i = block[1], block[2] do
      drop[i] = true
    end
  end
  local kept = {}
  for i, line in ipairs(lines) do
    if not drop[i] then
      table.insert(kept, line)
    end
  end
  return table.concat(kept, "\n")
end

-- The line a link to `name` sits in, as prose. The link to the note you are
-- reading becomes the words it displayed -- you already know the name -- while
-- every other link keeps its brackets, so the sentence still reads as one.
-- Truncation counts characters, not bytes: `sub` cuts a multi-byte tail in half
-- and the result goes straight into the panel buffer.
function M.context(text, name, max_len)
  max_len = max_len or 50
  for line in (text .. "\n"):gmatch("(.-)\n") do
    if wikilinks.count_to(line, name) > 0 then
      if vim.trim((line:gsub(wikilinks.SPAN, ""):gsub(ROW, ""))) == "" then
        return "(link only)"
      end
      local context = vim.trim((wikilinks.unwrap(line, name):gsub(ROW, "")))
      if vim.fn.strchars(context) > max_len then
        return vim.fn.strcharpart(context, 0, max_len) .. "…"
      end
      return context
    end
  end
  return ""
end

-- Notes that link to `name`, resolved exactly. `opts.context` also reads back the
-- line each links from, which only the panel wants -- it is a scan of every
-- candidate's text, and both other callers throw it away.
--
-- grep is only a prefilter, and it searches the bare name rather than `[[name`
-- so that `[[dir/name]]` and a differently-cased `[[Name]]` are still offered
-- up. Every candidate is then re-checked with the real resolution rules against
-- its *stripped* text, so prose mentions, `[[name-of-something-else]]` and a
-- candidate's own backlinks block all fall out again -- the last of those is
-- what stops every forward link coming back as a backlink.
function M.linking_notes(path, name, opts)
  opts = opts or {}
  local found = {}
  for _, candidate in ipairs(utils.grep_note_files(name, { ignorecase = true })) do
    if utils.resolve(candidate) ~= path then
      local text = utils.read_note(candidate)
      local authored = text and M.strip(text) or ""
      local count = wikilinks.count_to(authored, name)
      if count > 0 then
        table.insert(found, {
          path = candidate,
          name = utils.get_note_name(candidate),
          count = count,
          context = opts.context and M.context(authored, name, 40) or nil,
        })
      end
    end
  end
  table.sort(found, function(a, b)
    return a.name:lower() < b.name:lower()
  end)
  return found
end

-- A name `as_wikilink` refused to link -- one carrying a bracket, pipe or anchor,
-- any of which would forge a link to a different note -- is written in backticks
-- instead. The delimiter is what gives the row an identity that ends before an
-- annotation begins: keyed on the whole row text, annotating such a row changed
-- its key, so the row was reported removed and rewritten bare. A name carrying a
-- backtick as well falls back to whole-row keying, and keeps that rough edge.
local QUOTED = "^%s*[-*+]%s+`([^`]+)`"

-- `as_wikilink` returns the sanitized name unchanged when it refuses to link it,
-- so comparing against `sanitize` asks *it* whether the name was linked rather
-- than second-guessing its refusal class here. Testing the rendered text for
-- brackets would get `a[[b` wrong -- a name refused precisely for containing
-- them.
local function row_line(name)
  local safe = utils.sanitize(name)
  local link = utils.as_wikilink(name)
  if link ~= safe then
    return "- " .. link
  end
  return safe:find("`", 1, true) and ("- " .. safe) or ("- `" .. safe .. "`")
end

-- The note a row names, so a row still round-trips when it holds no wikilink.
-- Without a fallback such a row was re-added on every run while the old one was
-- absorbed as an annotation, growing the note without bound.
--
-- The backticks are read *before* any wikilink: a refused name can itself contain
-- `[[...]]` -- that is why it was refused -- and keying on the span inside the
-- quotes would key the row on the forged link rather than on the note.
local function row_identity(line)
  -- Exact, not eager: `row_line` quotes a name only when it holds one of these,
  -- so a user's `` `todo` `` on an ordinary row is an annotation, not the row.
  local quoted = line:match(QUOTED)
  if quoted and quoted:find("[%[%]|#]") then
    return vim.trim(quoted), vim.trim(quoted):lower()
  end
  local _, inner = line:match(wikilinks.SPAN)
  if inner and wikilinks.key(inner) ~= "" then
    return wikilinks.display(inner), wikilinks.key(inner)
  end
  local text = vim.trim((line:gsub(ROW, "")))
  return text, text:lower()
end

local function row_key(line)
  return select(2, row_identity(line))
end

-- The block's rows, keyed by the note each names, and whatever the user wrote
-- above the first row. A row is kept whole, so anything written on it survives a
-- refresh; a line under a row that is not itself a row travels with it, so a
-- multi-line annotation survives too. Only the generated heading and blank lines
-- are dropped -- a `#tag` on its own line is an annotation like any other.
function M.parse_rows(lines)
  local rows, preamble = {}, {}
  for _, line in ipairs(lines) do
    local trimmed = vim.trim(line)
    local name, key = "", ""
    if line:match(ROW_START) then
      name, key = row_identity(line)
    end
    if key ~= "" then
      table.insert(rows, { key = key, name = name, lines = { line } })
    elseif trimmed == M.HEADING or (trimmed == "" and #rows == 0 and #preamble == 0) then
      -- The heading and the blank line under it are regenerated by `render`;
      -- carrying them would double them. Every other blank line is the user's:
      -- one under a row, or between two paragraphs of a preamble, and dropping
      -- either collapsed their text while the message said "unchanged".
    elseif #rows > 0 then
      table.insert(rows[#rows].lines, line)
    else
      table.insert(preamble, line)
    end
  end
  return rows, preamble
end

-- Existing rows in their existing order, then the new ones. A row whose note no
-- longer links here is dropped and named: this edits the buffer, so `u` brings
-- it back before the note is written. A duplicate row is dropped too, but not
-- reported as removed -- the note it names is still listed.
function M.merge(existing, linked)
  local wanted, order = {}, {}
  for _, entry in ipairs(linked) do
    local line = row_line(entry.name)
    local key = row_key(line)
    wanted[key] = { key = key, name = entry.name, lines = { line } }
    table.insert(order, key)
  end
  local rows, added, removed, seen = {}, {}, {}, {}
  for _, row in ipairs(existing) do
    if seen[row.key] then
      -- A duplicate of a row already kept.
    elseif wanted[row.key] then
      seen[row.key] = true
      table.insert(rows, row)
    else
      table.insert(removed, row.name or row.key)
    end
  end
  for _, key in ipairs(order) do
    if not seen[key] then
      seen[key] = true
      table.insert(rows, wanted[key])
      table.insert(added, wanted[key].name)
    end
  end
  return rows, added, removed
end

function M.render(rows, preamble)
  local out = { M.OPEN, M.HEADING, "" }
  vim.list_extend(out, preamble or {})
  for _, row in ipairs(rows) do
    vim.list_extend(out, row.lines)
  end
  table.insert(out, M.CLOSE)
  return out
end

local function names(list)
  local shown = {}
  for i, name in ipairs(list) do
    if i > NAMED then
      table.insert(shown, string.format("and %d more", #list - NAMED))
      break
    end
    table.insert(shown, utils.sanitize(name))
  end
  return table.concat(shown, ", ")
end

local function describe(count, added, removed)
  local changes = {}
  if #added > 0 then
    table.insert(changes, string.format("+%d %s", #added, names(added)))
  end
  if #removed > 0 then
    table.insert(changes, string.format("-%d %s", #removed, names(removed)))
  end
  local summary = count == 1 and "1 backlink" or string.format("%d backlinks", count)
  if #changes == 0 then
    return summary .. ", unchanged"
  end
  return string.format("%s (%s)", summary, table.concat(changes, ", "))
end

-- Replace the block, or drop it when nothing links here any more. Appending
-- keeps one blank line before the block, and removing takes that line back. An
-- empty buffer is one empty line, which is written over rather than kept.
local function splice(lines, first, last, block)
  if first and #block == 0 then
    local from = first
    if from > 1 and vim.trim(lines[from - 1]) == "" then
      from = from - 1
    end
    vim.api.nvim_buf_set_lines(0, from - 1, last, false, {})
  elseif first then
    vim.api.nvim_buf_set_lines(0, first - 1, last, false, block)
  elseif #block > 0 then
    if #lines == 1 and lines[1] == "" then
      vim.api.nvim_buf_set_lines(0, 0, -1, false, block)
      return
    end
    local lead = vim.trim(lines[#lines] or "") ~= "" and { "" } or {}
    vim.api.nvim_buf_set_lines(0, #lines, #lines, false, vim.list_extend(lead, block))
  end
end

local function validate(path)
  if path == "" or not path:match("%.md$") then
    return "Not a markdown file"
  end
  if not utils.in_vault(path) then
    return "Not a note in " .. utils.vault_path
  end
  return nil
end

function M.update()
  local path = utils.resolve(vim.api.nvim_buf_get_name(0))
  local problem = validate(path)
  if problem then
    vim.notify(problem, vim.log.levels.WARN)
    return
  end

  local linked = M.linking_notes(path, utils.get_note_name(path))
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  local first, last = M.span(lines)
  local existing, preamble = {}, {}
  if first then
    existing, preamble = M.parse_rows(vim.list_slice(lines, first + 1, last - 1))
  end

  local rows, added, removed = M.merge(existing, linked)
  local keep = #rows > 0 or #preamble > 0
  splice(lines, first, last, keep and M.render(rows, preamble) or {})
  vim.notify(describe(#rows, added, removed), vim.log.levels.INFO)
end

function M.setup()
  vim.api.nvim_create_user_command("AriadneBacklinks", function()
    M.update()
  end, { desc = "Write the notes linking here into this note, as a managed block" })
end

return M
