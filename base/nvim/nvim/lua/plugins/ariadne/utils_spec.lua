-- Tests for the shared picker helpers. Run with:
--   :PlenaryBustedFile %
--   nvim --headless -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/utils_spec.lua"
--
-- These two functions are the only thing standing between a hostile note
-- filename and the editor, and both were wrong until a review caught them, so
-- they are the pieces worth pinning.
local utils = require("plugins.ariadne.utils")

describe("utils.sample", function()
  it("returns exactly count distinct elements", function()
    local picked = utils.sample({ "a", "b", "c", "d", "e" }, 3)
    assert.equals(3, #picked)
    local seen = {}
    for _, v in ipairs(picked) do
      assert.is_nil(seen[v])
      seen[v] = true
    end
  end)

  it("returns the whole list when asked for more than it holds", function()
    assert.equals(2, #utils.sample({ "a", "b" }, 5))
    assert.same({}, utils.sample({}, 5))
  end)

  it("leaves the source list alone", function()
    local source = { "a", "b", "c" }
    utils.sample(source, 2)
    assert.same({ "a", "b", "c" }, source)
  end)
end)

describe("utils.in_vault", function()
  -- nvim reports buffer names with symlinks resolved, so a vault configured
  -- through a symlink shared no prefix with its own notes and every gate using
  -- a bare startswith refused them. These pin the resolved comparison.
  local real, link

  before_each(function()
    real = vim.fn.tempname()
    link = vim.fn.tempname()
    vim.fn.mkdir(real, "p")
    vim.fn.mkdir(real .. "/sub", "p")
    assert(vim.uv.fs_symlink(real, link))
    vim.fn.writefile({ "Body." }, real .. "/note.md")
    Obsidian = { dir = link }
  end)

  after_each(function()
    Obsidian = nil
  end)

  it("accepts a note reached through the symlinked vault path", function()
    assert.is_true(utils.in_vault(link .. "/note.md"))
  end)

  it("accepts the same note named by its real path", function()
    assert.is_true(utils.in_vault(real .. "/note.md"))
  end)

  it("accepts a note not written to disk yet", function()
    assert.is_true(utils.in_vault(link .. "/brand-new.md"))
  end)

  it("accepts a note in a subdirectory", function()
    assert.is_true(utils.in_vault(link .. "/sub/nested.md"))
  end)

  it("rejects a path outside the vault", function()
    assert.is_false(utils.in_vault(vim.fn.tempname() .. "/elsewhere.md"))
  end)

  it("rejects the vault directory itself", function()
    assert.is_false(utils.in_vault(link))
  end)

  it("rejects a sibling whose name merely starts with the vault path", function()
    assert.is_false(utils.in_vault(real .. "-elsewhere/note.md"))
  end)

  it("rejects nil and the empty string", function()
    assert.is_false(utils.in_vault(nil))
    assert.is_false(utils.in_vault(""))
  end)
end)

describe("utils.run_ariadne_tool", function()
  local dir, argv_file, notified, real_notify

  local function write_tool(name, body)
    local path = dir .. "/" .. name
    vim.fn.writefile(vim.list_extend({ "#!/bin/sh", 'echo "$@" > ' .. argv_file }, body), path)
    vim.fn.setfperm(path, "rwxr-xr-x")
  end

  before_each(function()
    dir = vim.fn.tempname()
    vim.fn.mkdir(dir, "p")
    argv_file = dir .. "/argv.txt"
    vim.env.PATH = dir .. ":" .. vim.env.PATH
    Obsidian = { dir = dir }
    notified = {}
    real_notify = vim.notify
    vim.notify = function(msg, level)
      table.insert(notified, { msg = msg, level = level })
    end
  end)

  after_each(function()
    vim.notify = real_notify
    Obsidian = nil
    vim.fn.delete(dir, "rf")
  end)

  it("passes the vault first, then extra arguments, then --json", function()
    write_tool("ariadne-fake", { [[echo '{"orphans": []}']] })
    local decoded = utils.run_ariadne_tool("ariadne-fake", { "--since", "7d" }, { "orphans" })
    assert.same({}, decoded.orphans)
    assert.equals(dir .. " --since 7d --json", vim.trim(vim.fn.readfile(argv_file)[1]))
  end)

  it("returns nil when a required key is missing", function()
    write_tool("ariadne-fake", { [[echo '{"sparse": []}']] })
    assert.is_nil(utils.run_ariadne_tool("ariadne-fake", {}, { "orphans" }))
    assert.truthy(notified[#notified].msg:find("orphans"))
  end)

  it("returns nil on a non-zero exit, even with parseable output", function()
    write_tool("ariadne-fake", { [[echo '{"orphans": []}']], "exit 3" })
    assert.is_nil(utils.run_ariadne_tool("ariadne-fake", {}, { "orphans" }))
  end)

  it("returns nil on unparseable output", function()
    write_tool("ariadne-fake", { "echo not-json" })
    assert.is_nil(utils.run_ariadne_tool("ariadne-fake", {}, { "orphans" }))
  end)

  it("reports a missing tool at the caller's severity, naming what is lost", function()
    local decoded = utils.run_ariadne_tool("ariadne-absent", {}, { "orphans" }, {
      level = vim.log.levels.WARN,
      context = "the daily note's neglected section",
    })
    assert.is_nil(decoded)
    assert.equals(vim.log.levels.WARN, notified[1].level)
    assert.truthy(notified[1].msg:find("neglected section", 1, true))
  end)
end)

describe("utils.as_wikilink", function()
  it("wraps an ordinary note name", function()
    assert.equals("[[hubless-eight]]", utils.as_wikilink("hubless-eight"))
  end)

  it("cannot be made to write a second line", function()
    -- A newline in a filename survives ariadne-graph's JSON and would otherwise
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

describe("utils.write", function()
  local notified

  before_each(function()
    notified = {}
    ---@diagnostic disable-next-line: duplicate-set-field
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
    vim.cmd("enew!")
  end)

  it("writes to a path whose name contains a newline without running it", function()
    local dir = vim.fn.tempname()
    vim.fn.mkdir(dir, "p")
    local path = dir .. "/a\nNoSuchCmdHere.md"
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "body" })
    assert.is_true(utils.write(path))
    assert.equals("body", vim.fn.readfile(path)[1])
    assert.equals(0, #notified)
  end)

  it("reports failure rather than writing, so a caller can stop before deleting", function()
    -- M.rename deletes the original on the next line; a silent no-op here would
    -- destroy the note.
    assert.is_false(utils.write(nil))
    assert.is_false(utils.write(""))
    assert.is_false(utils.write(vim.NIL))
    assert.equals(3, #notified)
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
