-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/place_spec.lua"
--
-- Every vault here is a tempdir with `Obsidian.dir` pointed at it, as
-- branch_spec and delete_spec do, so nothing can reach the real vault.
--
-- `vim.system` is stubbed only for `ariadne-similar`; the `find` and `grep`
-- calls underneath `branch.taken_ids` and `commands.rename` go through to the
-- real one, because the ids already taken and the links already pointing at the
-- note are the two things this command has to get right and a stub would just
-- assert the fixture back at itself.
local place = require("plugins.ariadne.place")
local utils = require("plugins.ariadne.utils")

local vault, argv, notified
local real_system, real_notify, real_executable, real_input

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

local function entry(name, path, score, linked)
  return string.format(
    '{"name":%s,"path":%s,"score":%s,"linked":%s,"crosses":false,"cluster":1,"preview":"p"}',
    vim.json.encode(name),
    vim.json.encode(path),
    tostring(score),
    tostring(linked or false)
  )
end

local function payload(...)
  return '{"available":true,"error":null,"shape":null,"passage":null,'
    .. '"target":{"name":"loose","path":"/v/loose.md"},"similar":['
    .. table.concat({ ... }, ",")
    .. "]}"
end

-- Drives find_placement through to the picker and hands back what fzf-lua was
-- given. The callback runs inline, so nothing here is actually asynchronous.
local function run(json)
  local captured
  package.loaded["fzf-lua"] = {
    fzf_exec = function(lines, opts)
      captured = { lines = lines, opts = opts }
    end,
  }
  local real_schedule = vim.schedule
  vim.schedule = function(f)
    f()
  end
  vim.system = function(cmd, opts, cb)
    if cmd[1] == "ariadne-similar" then
      argv = cmd
      if cb then
        cb({ stdout = json, code = 0, stderr = "" })
      end
      return { wait = function() end }
    end
    return real_system(cmd, opts, cb)
  end
  place.find_placement()
  vim.schedule = real_schedule
  package.loaded["fzf-lua"] = nil
  return captured
end

-- The picker row whose proposed id is `id`, as fzf-lua would hand it back.
local function row_with(captured, id)
  for _, line in ipairs(captured.lines) do
    if line:match("^%S+%s+" .. vim.pesc(id) .. "%s") then
      return line
    end
  end
  return nil
end

local function ids(captured)
  local out = {}
  for _, line in ipairs(captured.lines) do
    table.insert(out, (line:match("^%S+%s+(%S+)")))
  end
  return out
end

local prefills
local function types(...)
  local answers = { ... }
  vim.fn.input = function(_, default)
    table.insert(prefills, default)
    return table.remove(answers, 1) or ""
  end
end

describe("place.find_placement", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    argv, notified, prefills = nil, {}, {}
    real_system, real_notify = vim.system, vim.notify
    real_executable, real_input = vim.fn.executable, vim.fn.input
    vim.fn.executable = function()
      return 1
    end
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
    types()
  end)

  after_each(function()
    vim.system, vim.notify = real_system, real_notify
    vim.fn.executable, vim.fn.input = real_executable, real_input
    _G.Obsidian = nil
    vim.cmd("silent! %bwipeout!")
  end)

  it("asks for a wide, unbridged, link-inclusive ranking", function()
    open_note("loose-note.md", "Body.\n")
    run(payload())
    -- --all and --no-bridge are the whole reason this is not :AriadneSimilar's
    -- query: bridging promotes the surprising neighbour over the nearest one,
    -- and a note already linked to its natural parent is the common case here.
    assert.same({
      "ariadne-similar",
      vim.api.nvim_buf_get_name(0),
      vault,
      "--all",
      "--no-bridge",
      "-n",
      "50",
      "--json",
    }, argv)
  end)

  it("sends a resolved note against an unresolved vault, as the CLI expects", function()
    -- The two path forms are deliberate, not a bug in the assertion: nvim
    -- reports a buffer's name with symlinks resolved while Obsidian.dir stays as
    -- configured, and `:AriadneSimilar` has always sent its target that way --
    -- the CLI copes, and passing a resolved vault instead would change the
    -- string the embedding cache is keyed on and force a full re-index. The
    -- literals are built here rather than from nvim_buf_get_name, which would
    -- assert the code's own expression back at itself.
    local real = vim.fn.tempname()
    vim.fn.mkdir(real, "p")
    local link = vim.fn.tempname()
    vim.fn.system({ "ln", "-s", real, link })
    _G.Obsidian = { dir = link }
    local f = assert(io.open(real .. "/loose-note.md", "w"))
    f:write("Body.\n")
    f:close()
    vim.cmd.edit({ args = { link .. "/loose-note.md" } })
    run(payload())
    assert.equals(vim.uv.fs_realpath(real) .. "/loose-note.md", argv[2])
    assert.equals(link, argv[3])
  end)

  it("offers a child and a sibling of each id-bearing neighbour", function()
    write("1a2 Parent.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84)))
    assert.same({ "1a2a", "1a3", "1" }, ids(captured))
    assert.is_truthy(row_with(captured, "1a2a"):find("child of", 1, true))
    assert.is_truthy(row_with(captured, "1a3"):find("sibling of", 1, true))
  end)

  it("ignores neighbours whose own names carry no id", function()
    write("1a2 Parent.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(
      entry("hub-note", vault .. "/hub-note.md", 0.91),
      entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84)
    ))
    assert.same({ "1a2a", "1a3", "1" }, ids(captured))
  end)

  it("skips ids already taken anywhere in the vault", function()
    write("1a2 Parent.md", "x\n")
    write("elsewhere/1a2a Taken.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84)))
    assert.same({ "1a2b", "1a3", "1" }, ids(captured))
  end)

  it("offers a slot once, however many neighbours reach it", function()
    -- sibling of 1a1 and sibling of 1a2 both walk to 1a3. Offering it twice
    -- would name a parent the second row's result would not sit next to.
    write("1a1 One.md", "x\n")
    write("1a2 Two.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(
      entry("1a1 One", vault .. "/1a1 One.md", 0.84),
      entry("1a2 Two", vault .. "/1a2 Two.md", 0.80)
    ))
    assert.same({ "1a1a", "1a3", "1a2a", "1" }, ids(captured))
  end)

  it("always offers a top-level slot, even with nothing to place under", function()
    write("1 First.md", "x\n")
    write("2 Second.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(entry("hub-note", vault .. "/hub-note.md", 0.91)))
    assert.same({ "3" }, ids(captured))
    assert.is_truthy(captured.lines[1]:find("new top-level sequence", 1, true))
    assert.is_truthy(captured.opts.fzf_opts["--header"]:find("0 of the 1 nearest", 1, true))
  end)

  -- Linkedness is the CLI's judgement, not this plugin's -- nothing in Lua
  -- computes it. The name says so, because a fixture with a real [[link]] in it
  -- would look like coverage of something untested.
  it("renders the linked flag the CLI sent", function()
    write("1a2 Parent.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84, true)))
    assert.is_truthy(row_with(captured, "1a2a"):find("[linked]", 1, true))
  end)

  it("files the placed note beside its parent, not where it was sitting", function()
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals(1, vim.fn.filereadable(vault .. "/seq/1a2a Working memory.md"))
    assert.equals(0, vim.fn.filereadable(vault .. "/inbox/loose-note.md"))
    assert.equals(
      "Branched from [[1a2 Parent]]\n\nBody.\n",
      utils.read_note(vault .. "/seq/1a2a Working memory.md")
    )
  end)

  it("links the placed note back to its new parent", function()
    -- The id implies the relationship; ariadne-graph counts wikilinks, so a
    -- placed note with no edge is an orphan by that measure.
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals(
      "Branched from [[1a2 Parent]]\n\nBody.\n",
      utils.read_note(vault .. "/seq/1a2a Working memory.md")
    )
  end)

  it("says a sibling continues, rather than branches from, its predecessor", function()
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a3") })
    assert.equals(
      "Continues [[1a2 Parent]]\n\nBody.\n",
      utils.read_note(vault .. "/seq/1a3 Working memory.md")
    )
  end)

  it("adds no link when the edge already exists in either direction", function()
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "See [[1a2 Parent]].\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84, true)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals(
      "See [[1a2 Parent]].\n",
      utils.read_note(vault .. "/seq/1a2a Working memory.md")
    )
  end)

  it("adds no link to a top-level placement, which has no parent", function()
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload())
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1") })
    assert.equals("Body.\n", utils.read_note(vault .. "/inbox/1 Working memory.md"))
  end)

  it("retargets every link to the note it just renamed", function()
    write("seq/1a2 Parent.md", "x\n")
    write("other.md", "See [[loose-note]] and [[loose-note|the loose one]].\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals(
      "See [[1a2a Working memory]] and [[1a2a Working memory|the loose one]].\n",
      utils.read_note(vault .. "/other.md")
    )
  end)

  it("renames a top-level placement in place, having no parent to join", function()
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload())
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1") })
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/1 Working memory.md"))
  end)

  it("cancels on an empty title, moving nothing", function()
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/loose-note.md"))
    assert.equals(0, #vim.fn.glob(vault .. "/seq/1a2a*", false, true))
    assert.is_truthy(notified[#notified]:find("Cancelled"))
  end)

  it("refuses a title that would escape the parent's directory", function()
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    types("../../../escaped")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.is_truthy(notified[#notified]:find("escapes its destination directory"))
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/loose-note.md"))
  end)

  it("refuses a placement whose parent sits outside the vault", function()
    -- The base handed to utils.vault_child is only a guard if the base itself is
    -- in the vault, and this one arrives in the CLI's JSON. The shipped CLI
    -- cannot emit such a path, which is exactly why nothing here may depend on
    -- that staying true.
    open_note("inbox/loose-note.md", "Body.\n")
    local outside = vim.fn.tempname()
    vim.fn.mkdir(outside, "p")
    local captured = run(payload(entry("1a2 Parent", outside .. "/1a2 Parent.md", 0.84)))
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.is_truthy(notified[#notified]:find("outside", 1, true))
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/loose-note.md"))
    assert.equals(0, vim.fn.filereadable(outside .. "/1a2a Working memory.md"))
  end)

  it("escapes the note's own name before offering it as the title", function()
    -- The prompt invites accepting the prefill with a bare Enter, and what it
    -- becomes is a filename -- so a bidi mark in the stem would let the cmdline
    -- render a name other than the bytes about to be written.
    write("1a2 Parent.md", "x\n")
    open_note("budget\226\128\174gnp.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84)))
    types("")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.equals("budget<U+202E>gnp", prefills[1])
  end)

  it("clamps a padded note name to its column instead of shifting the path", function()
    local name = "1a2 Parent" .. string.rep(" ", 60) .. "seq/decoy.md"
    write("1a2 Parent.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(entry(name, vault .. "/1a2 Parent.md", 0.84)))
    -- 6 (score) + 2 + 8 (id) + 1 + 11 (kind) + 1 + 40 (label) + 1 = 70.
    assert.equals("1a2 Parent.md", row_with(captured, "1a2a"):sub(71))
  end)

  it("skips a malformed entry rather than throwing inside the callback", function()
    write("1a2 Parent.md", "x\n")
    open_note("loose-note.md", "Body.\n")
    local captured = run(
      '{"available":true,"error":null,"shape":null,"passage":null,'
        .. '"target":{"name":"loose","path":"/v/loose.md"},"similar":[null,'
        .. '{"name":"1a9 No path","path":null,"score":0.9,"linked":false},'
        .. entry("1a2 Parent", vault .. "/1a2 Parent.md", 0.84)
        .. "]}"
    )
    assert.same({ "1a2a", "1a3", "1" }, ids(captured))
  end)

  it("refuses when the buffer was renamed while the picker was open", function()
    -- :saveas keeps the buffer handle, so a check on the handle alone passes and
    -- rename destroys a file the placement was never computed for.
    write("seq/1a2 Parent.md", "x\n")
    open_note("inbox/loose-note.md", "Body.\n")
    local captured = run(payload(entry("1a2 Parent", vault .. "/seq/1a2 Parent.md", 0.84)))
    vim.cmd.saveas({ args = { vault .. "/inbox/unrelated.md" } })
    types("Working memory")
    captured.opts.actions["default"]({ row_with(captured, "1a2a") })
    assert.is_truthy(notified[#notified]:find("no longer", 1, true))
    assert.equals(1, vim.fn.filereadable(vault .. "/inbox/unrelated.md"))
    assert.equals(0, vim.fn.filereadable(vault .. "/seq/1a2a Working memory.md"))
  end)

  it("caps how many neighbours become rows without understating the header", function()
    local args = {}
    for i = 1, 10 do
      local name = "1a" .. i .. " Parent " .. i
      write(name .. ".md", "x\n")
      table.insert(args, entry(name, vault .. "/" .. name .. ".md", 0.9 - i / 100))
    end
    open_note("loose-note.md", "Body.\n")
    local captured = run(payload(unpack(args)))
    -- 8 neighbours capped, but the header counts all 10 -- it exists to say how
    -- thin the evidence is, and must not understate it when it is richest.
    assert.is_truthy(captured.opts.fzf_opts["--header"]:find("10 of the 10 nearest", 1, true))
    local children = 0
    for _, line in ipairs(captured.lines) do
      if line:find("child of", 1, true) then
        children = children + 1
      end
    end
    assert.equals(8, children)
  end)

  it("refuses a note that already has an id", function()
    open_note("1a2 Already placed.md", "Body.\n")
    local captured = run(payload())
    assert.is_nil(argv)
    assert.is_nil(captured)
    assert.is_truthy(notified[#notified]:find("already has a Folgezettel id (1a2)", 1, true))
  end)

  it("refuses a buffer outside the vault", function()
    local outside = vim.fn.tempname() .. ".md"
    local f = assert(io.open(outside, "w"))
    f:write("Body.\n")
    f:close()
    vim.cmd.edit({ args = { outside } })
    run(payload())
    assert.is_nil(argv)
    assert.is_truthy(notified[#notified]:find("Not a note in"))
  end)

  it("warns that unsaved changes are not what gets ranked", function()
    open_note("loose-note.md", "Body.\n")
    vim.api.nvim_buf_set_lines(0, 0, -1, false, { "Edited but not written." })
    run(payload())
    assert.is_truthy(notified[1]:find("Unsaved changes", 1, true))
    assert.is_not_nil(argv)
  end)
end)
