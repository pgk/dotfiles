-- Reading the editor's visual selection.
--
-- Its own module rather than a corner of utils.lua: everything in utils.lua is
-- about the vault and the note files in it, while this is purely buffer state.
local M = {}

-- The text of the most recent visual selection, or nil if there is no range.
--
-- Read from the `'<` / `'>` marks rather than from a command's line range, so
-- the charwise columns survive -- a `range = true` command only ever sees whole
-- lines.
--
-- Deliberately no clamp on the end column: `string.sub` already saturates its
-- end index, so the clamp the earlier copy of this carried never did anything.
-- The load-bearing guard is the empty-`lines` check, which turns an
-- out-of-range or never-set mark pair into nil instead of a bad :sub().
-- Both were confirmed inert by mutation: removing either left every case in
-- selection_spec.lua passing.
function M.visual_selection(bufnr)
  local start_pos = vim.fn.getpos("'<")
  local end_pos = vim.fn.getpos("'>")
  local start_line, start_col = start_pos[2], start_pos[3]
  local end_line, end_col = end_pos[2], end_pos[3]

  local lines = vim.api.nvim_buf_get_lines(bufnr or 0, start_line - 1, end_line, false)
  if #lines == 0 then
    return nil
  end

  if #lines == 1 then
    lines[1] = lines[1]:sub(start_col, end_col)
  else
    lines[1] = lines[1]:sub(start_col)
    lines[#lines] = lines[#lines]:sub(1, end_col)
  end

  return table.concat(lines, "\n")
end

return M
