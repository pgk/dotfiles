-- Parsing `[[wikilinks]]` out of note text, and rewriting them.
--
-- The resolution rules mirror `ariadne_common.py` on the Python side: a link
-- names a note by basename, so `[[dir/a]]`, `[[a#heading]]` and `[[a|alias]]`
-- all resolve to `a`, case-insensitively. `commands.rewrite_links` predates this
-- and compares the raw inner text instead, so it silently misses the path and
-- anchor forms — don't copy it for anything destructive.
local M = {}

-- The whole span, brackets and any leading `!` included, so a match can be
-- replaced rather than only found. The inner class excludes both brackets, so
-- an unclosed `[[` is left alone instead of swallowing the rest of the note.
M.SPAN = "!?%[%[([^%[%]]*)%]%]"

local function split(inner)
  local target, alias = inner:match("^(.-)|(.*)$")
  if not target then
    target, alias = inner, nil
  end
  local head, anchor = target:match("^(.-)#(.*)$")
  if not head then
    head, anchor = target, nil
  end
  return head, anchor, alias
end

local function basename(path)
  return (path:gsub("\\", "/"):match("([^/]*)$"))
end

-- The key a link resolves by: basename, no anchor, lowercased. Empty for a link
-- that names no note, such as the same-note `[[#heading]]`.
function M.key(inner)
  local head = select(1, split(inner))
  return vim.trim(basename(head)):lower()
end

-- Precedence: alias, else the note's basename, else a same-note anchor's text.
function M.display(inner)
  local head, anchor, alias = split(inner)
  if alias and vim.trim(alias) ~= "" then
    return vim.trim(alias)
  end
  local name = vim.trim(basename(head))
  if name ~= "" then
    return name
  end
  return anchor and vim.trim(anchor) or ""
end

function M.count_to(text, name)
  local wanted = vim.trim(name):lower()
  local n = 0
  for inner in text:gmatch(M.SPAN) do
    if M.key(inner) == wanted then
      n = n + 1
    end
  end
  return n
end

-- Replace every link resolving to `name` with the words a reader saw there,
-- leaving every other link untouched. Returns the new text and the count.
function M.unwrap(text, name)
  local wanted = vim.trim(name):lower()
  local n = 0
  local out = text:gsub(M.SPAN, function(inner)
    if M.key(inner) ~= wanted then
      return nil -- gsub keeps the original span
    end
    n = n + 1
    return M.display(inner)
  end)
  return out, n
end

return M
