-- Tests for the shared picker helpers. Run with:
--   :PlenaryBustedFile %
--   nvim --headless -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/obsidian/utils_spec.lua"
--
-- These two functions are the only thing standing between a hostile note
-- filename and the editor, and both were wrong until a review caught them, so
-- they are the pieces worth pinning.
local utils = require("plugins.obsidian.utils")

describe("utils.as_wikilink", function()
  it("wraps an ordinary note name", function()
    assert.equals("[[hubless-eight]]", utils.as_wikilink("hubless-eight"))
  end)

  it("cannot be made to write a second line", function()
    -- A newline in a filename survives notes-graph's JSON and would otherwise
    -- land as its own line in the daily note, within the five lines nvim reads
    -- a modeline from -- in a file it opens immediately afterwards.
    local out = utils.as_wikilink("hub\nvim: set foldmethod=expr:")
    assert.is_nil(out:find("\n"))
    assert.equals("[[hub<0A>vim: set foldmethod=expr:]]", out)
  end)

  it("refuses link syntax to a name that could close the link early", function()
    assert.equals("a]] and [[b", utils.as_wikilink("a]] and [[b"))
    assert.equals("open[bracket", utils.as_wikilink("open[bracket"))
  end)

  it("handles nil without throwing", function()
    assert.equals("[[]]", utils.as_wikilink(nil))
  end)
end)

describe("utils.sanitize", function()
  it("leaves an ordinary note name untouched", function()
    assert.equals("hubless-eight", utils.sanitize("hubless-eight"))
    assert.equals("01 Top Of Mind", utils.sanitize("01 Top Of Mind"))
  end)

  it("is injective, so two names cannot render to the same picker row", function()
    -- The whole point: path_by_line is keyed on the rendered row, so collapsing
    -- control characters to spaces made selecting one row open another note.
    assert.are_not.equals(utils.sanitize("a\tb"), utils.sanitize("a b"))
    assert.are_not.equals(utils.sanitize("a\nb"), utils.sanitize("a b"))
  end)

  it("escapes control characters rather than blanking them", function()
    assert.equals("a<09>b", utils.sanitize("a\tb"))
    assert.equals("a<0A>b", utils.sanitize("a\nb"))
    assert.equals("a<1B>b", utils.sanitize("a\27b"))
  end)

  it("escapes the bidi and zero-width characters Lua's %c misses", function()
    -- %c is ASCII-only. U+202E reverses the rest of the row on screen, so a note
    -- can otherwise be displayed under a different apparent name than it opens.
    assert.equals("ev<U+202E>il", utils.sanitize("ev\226\128\174il"))
    assert.equals("a<U+200B>b", utils.sanitize("a\226\128\139b"))
    assert.equals("<U+FEFF>x", utils.sanitize("\239\187\191x"))
  end)

  it("handles nil and non-strings without throwing", function()
    assert.equals("", utils.sanitize(nil))
    assert.equals("42", utils.sanitize(42))
  end)
end)

describe("utils.edit", function()
  local notified

  before_each(function()
    notified = {}
    ---@diagnostic disable-next-line: duplicate-set-field
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
    vim.cmd("enew!")
  end)

  it("opens a path whose name contains a newline without running it", function()
    -- `vim.cmd("edit " .. fnameescape(path))` executed everything after the
    -- newline as an Ex command; the structured form takes it as an argument.
    local path = vim.fn.tempname() .. "/a\nNoSuchCmdHere.md"
    vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
    local ok = pcall(utils.edit, path)
    assert.is_true(ok)
    assert.is_true(vim.api.nvim_buf_get_name(0):find("\n", 1, true) ~= nil)
    assert.equals(0, #notified)
  end)

  it("refuses vim.NIL rather than opening a file called v:null", function()
    -- vim.json.decode maps a JSON null to vim.NIL, which is truthy, so a bare
    -- `if path then` guard would let it through and fnameescape would stringify it.
    local before = vim.api.nvim_buf_get_name(0)
    utils.edit(vim.NIL)
    assert.equals(before, vim.api.nvim_buf_get_name(0))
    assert.equals(1, #notified)
  end)

  it("refuses nil and the empty string", function()
    utils.edit(nil)
    utils.edit("")
    assert.equals(2, #notified)
  end)
end)
