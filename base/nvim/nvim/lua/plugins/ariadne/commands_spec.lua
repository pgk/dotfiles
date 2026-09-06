-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/commands_spec.lua"
--
-- `commands.rename` had no coverage until it grew a destination directory for
-- :AriadnePlace. It deletes the original and rewrites links across the whole
-- vault, so the cases worth pinning are the ones where it must NOT do half of
-- that. Every vault is a tempdir with `Obsidian.dir` pointed at it.
local commands = require("plugins.ariadne.commands")
local utils = require("plugins.ariadne.utils")

local vault, notified
local real_notify

local function write(rel, body)
  local path = vault .. "/" .. rel
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local f = assert(io.open(path, "w"))
  f:write(body)
  f:close()
  return path
end

local function open_note(rel, body)
  local path = write(rel, body)
  vim.cmd.edit({ args = { path } })
  return path
end

describe("commands.rename", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    notified = {}
    real_notify = vim.notify
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
  end)

  after_each(function()
    vim.notify = real_notify
    _G.Obsidian = nil
    vim.cmd("silent! %bwipeout!")
  end)

  it("renames in place and retargets the links pointing at it", function()
    write("other.md", "See [[old-name]] and [[old-name|an alias]].\n")
    open_note("old-name.md", "Body.\n")
    assert.is_true(commands.rename("new-name"))
    assert.equals(1, vim.fn.filereadable(vault .. "/new-name.md"))
    assert.equals(0, vim.fn.filereadable(vault .. "/old-name.md"))
    assert.equals(
      "See [[new-name]] and [[new-name|an alias]].\n",
      utils.read_note(vault .. "/other.md")
    )
  end)

  it("moves the note when given a destination directory", function()
    vim.fn.mkdir(vault .. "/seq", "p")
    open_note("inbox/old-name.md", "Body.\n")
    assert.is_true(commands.rename("1a2a New name", { dir = vault .. "/seq" }))
    assert.equals(1, vim.fn.filereadable(vault .. "/seq/1a2a New name.md"))
    assert.equals(0, vim.fn.filereadable(vault .. "/inbox/old-name.md"))
  end)

  it("refuses a name that escapes the directory it renames into", function()
    -- This path had no guard at all before: it concatenated the name straight
    -- onto the directory, and rename deletes the original, so an escaping name
    -- moved the note out with no copy left behind.
    open_note("inbox/old-name.md", "Body.\n")
    assert.is_false(commands.rename("../../../escaped"))
    assert.is_truthy(notified[#notified]:find("escapes its destination directory"))
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/old-name.md"))
  end)

  it("refuses a destination that already exists, changing nothing", function()
    write("taken.md", "Other note.\n")
    write("other.md", "See [[old-name]].\n")
    open_note("old-name.md", "Body.\n")
    assert.is_false(commands.rename("taken"))
    assert.equals("Other note.\n", utils.read_note(vault .. "/taken.md"))
    assert.equals("See [[old-name]].\n", utils.read_note(vault .. "/other.md"))
    assert.equals(1, vim.fn.filereadable(vault .. "/old-name.md"))
  end)

  it("leaves every link alone when the destination cannot be written", function()
    -- The write is the step that can still fail, and it used to run *after* the
    -- whole vault had been retargeted -- so a failure left the original note in
    -- place with every link to it already pointing at a name that did not exist.
    write("other.md", "See [[old-name]].\n")
    open_note("old-name.md", "Body.\n")
    -- utils.write returns false rather than letting E212 propagate: this is
    -- reached from an fzf-lua action, where a traceback lands on the user.
    assert.is_false(commands.rename("new-name", { dir = vault .. "/no-such-dir" }))
    assert.equals("See [[old-name]].\n", utils.read_note(vault .. "/other.md"))
    assert.equals(1, vim.fn.filereadable(vault .. "/old-name.md"))
  end)

  it("refuses a buffer that is not markdown", function()
    open_note("note.txt", "Body.\n")
    assert.is_false(commands.rename("whatever"))
    assert.is_truthy(notified[#notified]:find("Not a markdown file"))
  end)
end)

describe("commands.extract_note", function()
  -- Every case here would have thrown before: selection.lua was split out of
  -- extract_note and its four range locals were left behind, undefined, so the
  -- replace step errored on every run -- after the note had already been written.
  local real_input

  local function types(answer)
    vim.fn.input = function()
      return answer
    end
  end

  local function select_in(buf, start_line, start_col, end_line, end_col)
    vim.fn.setpos("'<", { buf, start_line, start_col, 0 })
    vim.fn.setpos("'>", { buf, end_line, end_col, 0 })
  end

  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    notified = {}
    real_notify, real_input = vim.notify, vim.fn.input
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
  end)

  after_each(function()
    vim.notify, vim.fn.input = real_notify, real_input
    _G.Obsidian = nil
    vim.cmd("silent! %bwipeout!")
  end)

  it("writes the selection to a new note and leaves a link behind", function()
    local path = write("source.md", "one two\nmiddle\nthree four\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 1, 5, 3, 5)
    types("extracted idea")
    commands.extract_note()
    assert.equals("two\nmiddle\nthree\n", utils.read_note(vault .. "/extracted idea.md"))
    assert.same({ "one [[extracted idea]] four" }, vim.api.nvim_buf_get_lines(0, 0, -1, false))
  end)

  it("replaces exactly the selected span, keeping a multi-byte tail whole", function()
    local path = write("source.md", "héllo wörld\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 1, 1, 1, 2)
    types("greeting")
    commands.extract_note()
    assert.equals("hé\n", utils.read_note(vault .. "/greeting.md"))
    assert.same({ "[[greeting]]llo wörld" }, vim.api.nvim_buf_get_lines(0, 0, -1, false))
  end)

  it("does not let a bracketed name forge a link", function()
    local path = write("source.md", "one two\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 1, 1, 1, 3)
    types("a]] [[elsewhere")
    commands.extract_note()
    assert.same({ "a]] [[elsewhere two" }, vim.api.nvim_buf_get_lines(0, 0, -1, false))
  end)

  it("refuses a name that escapes the vault, writing nothing", function()
    local path = write("source.md", "one two\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 1, 1, 1, 3)
    types("../../../escaped")
    commands.extract_note()
    assert.is_truthy(notified[#notified]:find("escapes the vault"))
    assert.same({ "one two" }, vim.api.nvim_buf_get_lines(0, 0, -1, false))
  end)

  it("cancels on an empty name, leaving the buffer alone", function()
    local path = write("source.md", "one two\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 1, 1, 1, 3)
    types("")
    commands.extract_note()
    assert.is_truthy(notified[#notified]:find("cancelled"))
    assert.same({ "one two" }, vim.api.nvim_buf_get_lines(0, 0, -1, false))
  end)

  it("refuses when there is no selection at all", function()
    local path = write("source.md", "one two\n")
    vim.cmd.edit({ args = { path } })
    select_in(vim.api.nvim_get_current_buf(), 0, 0, 0, 0)
    commands.extract_note()
    assert.is_truthy(notified[#notified]:find("No text selected"))
  end)
end)
