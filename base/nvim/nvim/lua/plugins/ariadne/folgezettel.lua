-- Luhmann's branching note ids: `1`, `1a`, `1a1`, `1a1a`, ...
--
-- An id alternates digit and letter segments, starting with digits. Depth is
-- how many segments it has, so a *child* appends a segment of the other kind
-- (`1a` -> `1a1`) and a *sibling* increments the last one (`1a` -> `1b`). That
-- is the whole grammar; everything else here is carrying.
local M = {}

-- Segments, or nil if `id` is not a well-formed alternating sequence. Anything
-- left over means it isn't one, so "1a-2" and "1a " are rejected rather than
-- half-parsed.
function M.segments(id)
  if type(id) ~= "string" or id == "" then
    return nil
  end
  local parts, rest, want_digits = {}, id, true
  while rest ~= "" do
    local seg = rest:match(want_digits and "^%d+" or "^%l+")
    if not seg then
      return nil
    end
    table.insert(parts, seg)
    rest = rest:sub(#seg + 1)
    want_digits = not want_digits
  end
  return parts
end

-- `1a Working memory` -> "1a", "Working memory". Nil when the stem does not
-- open with an id, which is how a note opts out of the scheme.
function M.split(stem)
  if type(stem) ~= "string" then
    return nil
  end
  local id, title = stem:match("^(%S+)%s+(.*)$")
  if not id then
    id, title = stem, ""
  end
  if not M.segments(id) then
    return nil
  end
  return id, title
end

-- Bijective base-26: z -> aa, az -> ba, zz -> aaa. Not a carry into a new
-- digit segment -- letters and digits alternate by depth, so a letter segment
-- can only ever grow wider.
local function next_letters(letters)
  local chars = {}
  for c in letters:gmatch(".") do
    table.insert(chars, c)
  end
  for i = #chars, 1, -1 do
    if chars[i] ~= "z" then
      chars[i] = string.char(chars[i]:byte() + 1)
      return table.concat(chars)
    end
    chars[i] = "a"
  end
  return "a" .. table.concat(chars)
end

-- The first child: one level deeper, so a segment of the opposite kind.
function M.child(id)
  local parts = M.segments(id)
  if not parts then
    return nil
  end
  return id .. (#parts % 2 == 1 and "a" or "1")
end

-- The next sibling: same depth, last segment incremented.
function M.sibling(id)
  local parts = M.segments(id)
  if not parts then
    return nil
  end
  local last = parts[#parts]
  local bumped = last:match("^%d+$") and tostring(tonumber(last) + 1) or next_letters(last)
  return id:sub(1, #id - #last) .. bumped
end

-- The first id at or after `start` that `taken` does not contain. `taken` is
-- keyed by lowercased id. Walks by sibling, which is the right step for both
-- kinds: the second child of `1a` is `1a2`, the second sibling is `1c`.
function M.first_free(start, taken)
  local candidate = start
  while candidate and taken[candidate:lower()] do
    candidate = M.sibling(candidate)
  end
  return candidate
end

return M
