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
-- The bang is captured, not just matched: `retarget` has to put it back, or
-- rewriting `![[old]]` would silently demote an embed to a plain link.
M.SPAN = "(!?)%[%[([^%[%]]*)%]%]"

local function split(inner)
  local target, alias = inner:match("^(.-)|(.*)$")
  target = target or inner
  local head, anchor = target:match("^(.-)#(.*)$")
  return head or target, anchor, alias
end

local function basename(path)
  return (path:gsub("\\", "/"):match("([^/]*)$"))
end

-- The key a link resolves by: basename, no anchor, lowercased. Empty for a link
-- that names no note, such as the same-note `[[#heading]]`.
function M.key(inner)
  local head = split(inner)
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
  for _, inner in text:gmatch(M.SPAN) do
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
  local out = text:gsub(M.SPAN, function(_, inner)
    if M.key(inner) ~= wanted then
      return nil -- gsub keeps the original span
    end
    n = n + 1
    return M.display(inner)
  end)
  return out, n
end

-- Every distinct note this text links to, as resolution keys.
function M.targets(text)
  local keys, seen = {}, {}
  for _, inner in text:gmatch(M.SPAN) do
    local key = M.key(inner)
    if key ~= "" and not seen[key] then
      seen[key] = true
      table.insert(keys, key)
    end
  end
  return keys
end

-- Point every link resolving to `old` at `new`, keeping the anchor, the alias
-- and the embed bang. Returns the new text and the count. Refuses a `new`
-- containing a bracket for the reason `utils.as_wikilink` documents: a "]]" in
-- the name would close the link early and forge a link to something else.
function M.retarget(text, old, new)
  if new:find("[%[%]|#]") then
    return text, 0
  end
  local wanted = vim.trim(old):lower()
  local n = 0
  local out = text:gsub(M.SPAN, function(bang, inner)
    if M.key(inner) ~= wanted then
      return nil
    end
    local _, anchor, alias = split(inner)
    n = n + 1
    return bang
      .. "[["
      .. new
      .. (anchor and ("#" .. anchor) or "")
      .. (alias and ("|" .. alias) or "")
      .. "]]"
  end)
  return out, n
end

return M
