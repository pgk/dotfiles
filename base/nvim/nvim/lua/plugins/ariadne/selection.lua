-- Reading the editor's visual selection.
--
-- Its own module rather than a corner of utils.lua: everything in utils.lua is
-- about the vault and the note files in it, while this is purely buffer state.
local M = {}

-- The `'<` / `'>` marks as a byte range, or nil if there is no range.
--
-- Shaped for the nvim_buf_*_text API: 0-based rows, 0-based end-exclusive
-- columns, clamped to lines that actually exist. Read from the marks rather than
-- from a command's line range, so the charwise columns survive -- a
-- `range = true` command only ever sees whole lines.
--
-- Its own function because `commands.extract_note` needs the range and not just
-- the text: it replaces the selection with a link, and a range recomputed
-- separately could disagree with the text that was extracted.
function M.visual_range(bufnr)
  local start_pos = vim.fn.getpos("'<")
  local end_pos = vim.fn.getpos("'>")
  local start_line, start_col = start_pos[2], start_pos[3]
  local end_line, end_col = end_pos[2], end_pos[3]

  local lines = vim.api.nvim_buf_get_lines(bufnr or 0, start_line - 1, end_line, false)
  -- The load-bearing guard: an out-of-range or never-set mark pair lands here,
  -- rather than producing a range that addresses nothing.
  if #lines == 0 then
    return nil
  end

  -- `'>` points at the FIRST byte of the last selected character, and a linewise
  -- V selection reports v:maxcol instead of a column at all. Clamp to the line,
  -- then extend to the end of the character that byte belongs to -- an index
  -- landing inside a multi-byte character would cut it in half, which
  -- nvim_buf_set_text writes to the buffer as invalid UTF-8.
  local last = lines[#lines]
  local stop = math.min(end_col, #last)
  if stop >= 1 then
    stop = stop + vim.str_utf_end(last, stop)
  end

  return {
    start_row = start_line - 1,
    start_col = math.min(start_col - 1, #lines[1]),
    -- Not `end_line - 1`: the marks may reach past the end of the buffer, and
    -- `lines` is what actually came back.
    end_row = start_line - 1 + #lines - 1,
    end_col = stop,
  }
end

-- The text `range` covers.
function M.text_in(bufnr, range)
  return table.concat(
    vim.api.nvim_buf_get_text(
      bufnr or 0, range.start_row, range.start_col, range.end_row, range.end_col, {}
    ),
    "\n"
  )
end

-- The text of the most recent visual selection, or nil if there is no range.
--
-- Goes through `visual_range` and `nvim_buf_get_text` rather than slicing the
-- lines itself, so the text and the range can never describe different regions.
function M.visual_selection(bufnr)
  local range = M.visual_range(bufnr)
  if not range then
    return nil
  end
  return M.text_in(bufnr, range)
end

return M
