-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/branch_spec.lua"
--
-- Every vault here is a tempdir, with `Obsidian.dir` pointed at it so nothing
-- can reach the real vault.
local branch = require("plugins.ariadne.branch")
local utils = require("plugins.ariadne.utils")

local vault, notified
local real_input = vim.fn.input

local function write(rel, body)
  local path = vault .. "/" .. rel
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local f = assert(io.open(path, "w"))
  f:write(body)
  f:close()
  return path
end

-- The title prompt blocks, so each test declares its answers up front.
local function types(...)
  local answers = { ... }
  vim.fn.input = function()
    return table.remove(answers, 1) or ""
  end
end

local function opened()
  return vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":t")
end

describe("branch.create", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    notified = {}
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
    types()
  end)

  after_each(function()
    _G.Obsidian = nil
    vim.fn.input = real_input
  end)

  it("creates the first child one level deeper", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("Working memory limits")
    branch.create("child")
    assert.equals("1a1 Working memory limits.md", opened())
  end)

  it("creates the next sibling at the same level", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("A different line")
    branch.create("sibling")
    assert.equals("1b A different line.md", opened())
  end)

  it("skips ids already taken", function()
    write("1a1 Taken.md", "x\n")
    write("1a2 Also taken.md", "x\n")
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("Third")
    branch.create("child")
    assert.equals("1a3 Third.md", opened())
  end)

  it("counts ids anywhere in the vault, not just beside the parent", function()
    write("elsewhere/1b Taken.md", "x\n")
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("Next")
    branch.create("sibling")
    assert.equals("1c Next.md", opened())
  end)

  it("links the new note back to its parent", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("Child")
    branch.create("child")
    assert.equals("Branched from [[1a Note title]]\n\n", utils.read_note(vault .. "/1a1 Child.md"))
  end)

  it("says a sibling continues, rather than branches from, its predecessor", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("Sibling")
    branch.create("sibling")
    assert.equals("Continues [[1a Note title]]\n\n", utils.read_note(vault .. "/1b Sibling.md"))
  end)

  it("creates the note beside its parent, not at the vault root", function()
    utils.edit(write("seq/1a Note title.md", "Body.\n"))
    types("Child")
    branch.create("child")
    assert.equals(1, vim.fn.filereadable(vault .. "/seq/1a1 Child.md"))
    assert.equals(0, vim.fn.filereadable(vault .. "/1a1 Child.md"))
  end)

  it("leaves the parent untouched", function()
    local parent = write("1a Note title.md", "Body.\n")
    utils.edit(parent)
    types("Child")
    branch.create("child")
    assert.equals("Body.\n", utils.read_note(parent))
  end)

  it("refuses a note with no Folgezettel id", function()
    utils.edit(write("hub-note.md", "Body.\n"))
    types("Child")
    branch.create("child")
    assert.is_truthy(notified[#notified]:find("no Folgezettel id"))
    assert.equals(0, #vim.fn.glob(vault .. "/*Child*", false, true))
  end)

  it("cancels on an empty title", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("")
    branch.create("child")
    assert.equals("1a Note title.md", opened())
    assert.is_truthy(notified[#notified]:find("Cancelled"))
  end)

  it("refuses a title that would escape the vault", function()
    utils.edit(write("1a Note title.md", "Body.\n"))
    types("../../../escaped")
    branch.create("child")
    assert.is_truthy(notified[#notified]:find("escapes the vault"))
  end)

  it("refuses a buffer outside the vault", function()
    local outside = vim.fn.tempname() .. ".md"
    local f = assert(io.open(outside, "w"))
    f:write("1a elsewhere\n")
    f:close()
    utils.edit(outside)
    branch.create("child")
    assert.is_truthy(notified[#notified]:find("Not a note in"))
  end)
end)
