-- Custom formatexpr for Obsidian vault markdown files.
-- Prevents gw from breaking [[wiki links]] across lines.
local utils = require("plugins.obsidian.utils")

local M = {}

-- Detect whether line `lnum` (1-indexed) is inside a fenced code block by
-- counting ``` fence markers in lines 1..(lnum-1). An odd count means we're
-- inside a block.
local function in_fenced_code_block(lnum)
  local lines = vim.api.nvim_buf_get_lines(0, 0, lnum - 1, false)
  local fence_count = 0
  for _, line in ipairs(lines) do
    if line:match("^```") then
      fence_count = fence_count + 1
    end
  end
  return (fence_count % 2) == 1
end

-- Extract the prefix (leading whitespace + list/blockquote marker) from the
-- first line of a paragraph, and compute the continuation indent (spaces that
-- align wrapped lines with the body text after the marker).
-- Returns: prefix (string), continuation_indent (string), body_start (string)
local function extract_prefix(first_line)
  -- Ordered list: "  1. ", "1. ", etc.
  local indent, marker, rest = first_line:match("^(%s*)(%d+%.%s+)(.*)")
  if indent and marker then
    local cont = string.rep(" ", #indent + #marker)
    return indent .. marker, cont, rest
  end

  -- Unordered list with - or *: "  - ", "* ", etc.
  indent, marker, rest = first_line:match("^(%s*)([-*]%s+)(.*)")
  if indent and marker then
    local cont = string.rep(" ", #indent + #marker)
    return indent .. marker, cont, rest
  end

  -- Blockquote: "> "
  indent, marker, rest = first_line:match("^(%s*)(>%s*)(.*)")
  if indent and marker then
    local cont = string.rep(" ", #indent + #marker)
    return indent .. marker, cont, rest
  end

  -- Plain indent (leading whitespace only)
  local leading, body = first_line:match("^(%s+)(.*)")
  if leading then
    return leading, leading, body
  end

  -- No prefix
  return "", "", first_line
end

-- Replace all [[...]] occurrences in `text` with sentinel placeholders of the
-- same byte length. Returns the modified text and an ordered list of originals.
local function placeholderize(text)
  local originals = {}
  local result = text:gsub("%[%[[^%]]*%]%]", function(link)
    table.insert(originals, link)
    return string.rep("\1", #link)
  end)
  return result, originals
end

-- Restore placeholders (contiguous \1 runs) back to original [[...]] links.
local function restore_placeholders(text, originals)
  local idx = 0
  local result = text:gsub("\1+", function()
    idx = idx + 1
    return originals[idx] or ""
  end)
  return result
end

-- Word-wrap `body` at `width` columns, prefixing the first line with `prefix`
-- and subsequent lines with `continuation`. Words containing \1 are placeholders
-- and must never be broken.
local function wrap_body(body, width, prefix, continuation)
  local words = {}
  for word in body:gmatch("%S+") do
    table.insert(words, word)
  end

  local lines = {}
  local current_prefix = prefix
  local current = current_prefix
  local available = width - #current_prefix

  for _, word in ipairs(words) do
    if current == current_prefix then
      -- First word on a new line: always place it here, even if it overflows
      current = current .. word
    elseif #word + 1 <= width - #current then
      -- Word fits after a space
      current = current .. " " .. word
    else
      -- Word does not fit: flush current line and start a new one
      table.insert(lines, current)
      current_prefix = continuation
      current = current_prefix .. word
      available = width - #current_prefix
    end
    -- Suppress unused variable warning for `available`
    _ = available
  end

  if current ~= continuation and current ~= prefix then
    table.insert(lines, current)
  elseif #lines == 0 then
    -- Empty body: emit at least the prefix line
    table.insert(lines, current_prefix)
  end

  return lines
end

-- The formatexpr implementation. Neovim calls this with v:lnum and v:count set.
function M.formatexpr()
  local lnum = vim.v.lnum
  local count = vim.v.count

  -- Guard: only act inside the vault on markdown files
  local filepath = vim.api.nvim_buf_get_name(0)
  local vault = utils.vault_path
  if not filepath:match(vim.pesc(vault)) then
    return 1
  end

  -- Guard: don't format inside fenced code blocks
  if in_fenced_code_block(lnum) then
    return 1
  end

  -- Retrieve the lines to format (0-indexed for nvim_buf_get_lines)
  local raw_lines = vim.api.nvim_buf_get_lines(0, lnum - 1, lnum - 1 + count, false)
  if #raw_lines == 0 then
    return 1
  end

  -- Detect prefix from the first line
  local prefix, continuation, first_body = extract_prefix(raw_lines[1])

  -- Join all lines into a single body string
  local body_parts = { first_body }
  for i = 2, #raw_lines do
    local stripped = raw_lines[i]:match("^%s*(.*)")
    table.insert(body_parts, stripped)
  end
  local body = table.concat(body_parts, " ")

  -- Collapse multiple spaces into one (can arise from joining lines)
  body = body:gsub("%s+", " "):match("^%s*(.-)%s*$")

  -- Determine target width
  local tw = vim.bo.textwidth
  if tw == nil or tw == 0 then
    tw = 80
  end

  -- Replace [[wiki links]] with placeholders
  local placeholder_body, originals = placeholderize(body)

  -- Word-wrap
  local wrapped = wrap_body(placeholder_body, tw, prefix, continuation)

  -- Restore [[wiki links]]
  -- We need to restore across all lines combined, since a placeholder may not
  -- be split (the wrap_body function guarantees this), so we can restore
  -- line-by-line in order.
  local restored = {}
  local global_idx = 0
  for _, line in ipairs(wrapped) do
    local result = line:gsub("\1+", function()
      global_idx = global_idx + 1
      return originals[global_idx] or ""
    end)
    table.insert(restored, result)
  end

  -- Replace lines in the buffer
  vim.api.nvim_buf_set_lines(0, lnum - 1, lnum - 1 + count, false, restored)

  return 0
end

function M.setup()
  -- No-op: formatexpr is set by the caller (autocmd in init.lua)
end

return M
