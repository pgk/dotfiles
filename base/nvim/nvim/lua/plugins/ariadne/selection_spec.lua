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

  it("keeps a multi-byte last character whole", function()
    -- `'>` points at the FIRST byte of the last selected character, so a range
    -- ending there cuts a multi-byte character in half. Text-side that is a
    -- mangled string; range-side nvim_buf_set_text writes invalid UTF-8.
    select_in({ "héllo" }, 1, 1, 1, 2)
    assert.equals("hé", selection.visual_selection())
  end)
end)

describe("selection.visual_range", function()
  it("is 0-based with an end-exclusive column, for nvim_buf_set_text", function()
    select_in({ "hello brave world" }, 1, 7, 1, 11)
    assert.same({ start_row = 0, start_col = 6, end_row = 0, end_col = 11 }, selection.visual_range())
  end)

  it("clamps the v:maxcol a linewise V selection reports", function()
    select_in({ "short" }, 1, 1, 1, 2147483647)
    assert.same({ start_row = 0, start_col = 0, end_row = 0, end_col = 5 }, selection.visual_range())
  end)

  it("extends the end past a multi-byte character rather than into it", function()
    select_in({ "héllo" }, 1, 1, 1, 2)
    -- é occupies bytes 2-3, so the exclusive end is 3, not 2.
    assert.equals(3, selection.visual_range().end_col)
  end)

  it("ends at the last line that exists, not the one the mark names", function()
    select_in({ "one", "two" }, 1, 1, 9, 2147483647)
    local range = selection.visual_range()
    assert.equals(1, range.end_row)
    assert.equals(3, range.end_col)
  end)

  it("is nil on the same terms as visual_selection", function()
    select_in({ "only line" }, 40, 1, 41, 5)
    assert.is_nil(selection.visual_range())
  end)

  -- The round trip is the point: extract_note writes the text into a new note
  -- and replaces exactly this range with a link, so they must not disagree.
  it("addresses exactly the text visual_selection returns", function()
    local buf = select_in({ "one two", "middle", "three four" }, 1, 5, 3, 5)
    local range = selection.visual_range()
    local text = selection.visual_selection()
    vim.api.nvim_buf_set_text(buf, range.start_row, range.start_col, range.end_row, range.end_col, { "X" })
    assert.equals("two\nmiddle\nthree", text)
    assert.same({ "one X four" }, vim.api.nvim_buf_get_lines(buf, 0, -1, false))
  end)
end)
