-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/selection_spec.lua"
--
-- These pin behaviour, not implementation: what a linewise (`v:maxcol`) or `$`
-- selection must return, and what an out-of-range mark pair must return. The
-- logic lived unreachable inside commands.extract_note() until now.
local selection = require("plugins.ariadne.selection")

-- Marks are set directly rather than driven through visual mode: feedkeys in a
-- headless test would depend on mapping state, and '< / '> are exactly what the
-- function reads anyway.
local function select_in(lines, start_line, start_col, end_line, end_col)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  vim.api.nvim_set_current_buf(buf)
  vim.fn.setpos("'<", { buf, start_line, start_col, 0 })
  vim.fn.setpos("'>", { buf, end_line, end_col, 0 })
  return buf
end

describe("selection.visual_selection", function()
  it("returns the selected part of a single line", function()
    select_in({ "hello brave world" }, 1, 7, 1, 11)
    assert.equals("brave", selection.visual_selection())
  end)

  it("keeps the head of the first line and the tail of the last", function()
    select_in({ "one two", "middle", "three four" }, 1, 5, 3, 5)
    assert.equals("two\nmiddle\nthree", selection.visual_selection())
  end)

  it("returns the whole line for the v:maxcol end column a linewise V selection reports", function()
    select_in({ "short" }, 1, 1, 1, 2147483647)
    assert.equals("short", selection.visual_selection())
  end)

  it("bounds the last line by its own length, not the first line's", function()
    -- The regression this guards: any bound computed from line 1 ("a long first
    -- line") and applied to line 2 truncates the wrong string. A clamp written
    -- against #lines[1] instead of #lines[#lines] fails here.
    select_in({ "a long first line", "tiny" }, 1, 1, 2, 2147483647)
    assert.equals("a long first line\ntiny", selection.visual_selection())
  end)

  it("handles a charwise selection ending at $", function()
    select_in({ "abc", "defgh" }, 1, 2, 2, 5)
    assert.equals("bc\ndefgh", selection.visual_selection())
  end)

  it("selects a single character", function()
    select_in({ "abc" }, 1, 2, 1, 2)
    assert.equals("b", selection.visual_selection())
  end)

  it("returns an empty string for an empty line, rather than nothing at all", function()
    -- Distinct from nil: the line exists and was selected, it just has no text.
    select_in({ "" }, 1, 1, 1, 2147483647)
    assert.equals("", selection.visual_selection())
  end)

  it("is nil when the marks are unset, as before any visual selection", function()
    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "text" })
    vim.api.nvim_set_current_buf(buf)
    vim.fn.setpos("'<", { buf, 0, 0, 0 })
    vim.fn.setpos("'>", { buf, 0, 0, 0 })
    assert.is_nil(selection.visual_selection())
  end)

  it("is nil when the marks point past the end of the buffer", function()
    select_in({ "only line" }, 40, 1, 41, 5)
    assert.is_nil(selection.visual_selection())
  end)
end)
