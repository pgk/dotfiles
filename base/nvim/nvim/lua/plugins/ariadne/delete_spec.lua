-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/delete_spec.lua"
--
-- Every vault here is a tempdir. `Obsidian.dir` is set to it so that
-- `utils.vault_path` — and the grep inside it — cannot reach the real vault.
local delete = require("plugins.ariadne.delete")
local utils = require("plugins.ariadne.utils")

local vault, answers, asked, notified

local function write(rel, text)
  local path = vault .. "/" .. rel
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local f = assert(io.open(path, "w"))
  f:write(text)
  f:close()
  return path
end

local function read(path)
  local f = io.open(path, "r")
  if not f then
    return nil
  end
  local text = f:read("*a")
  f:close()
  return text
end

-- `vim.fn.confirm` blocks on a real prompt, so each test declares its answers up
-- front: one per prompt, in the order they are raised.
local function answer(...)
  answers = { ... }
  asked = {}
  vim.fn.confirm = function(prompt, _, _, _)
    table.insert(asked, prompt)
    return table.remove(answers, 1) or 0
  end
end

local real_confirm = vim.fn.confirm

describe("delete.delete", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    notified = {}
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
    answer()
  end)

  after_each(function()
    _G.Obsidian = nil
    vim.fn.confirm = real_confirm
  end)

  local function open(path)
    utils.edit(path)
  end

  local function trashed(name)
    return read(vault .. "/.trash/" .. name)
  end

  it("moves an unlinked note to .trash without asking", function()
    local path = write("lonely.md", "Nothing points here.\n")
    open(path)
    delete.delete()
    assert.equals(0, #asked)
    assert.equals(0, vim.fn.filereadable(path))
    assert.equals("Nothing points here.\n", trashed("lonely.md"))
  end)

  it("asks before deleting a linked note, and cancelling changes nothing", function()
    local path = write("linked.md", "Body.\n")
    write("other.md", "See [[linked]] here.\n")
    open(path)
    answer(2) -- Cancel
    delete.delete()
    assert.equals(1, #asked)
    assert.equals(1, vim.fn.filereadable(path))
    assert.is_nil(trashed("linked.md"))
  end)

  it("names the linking notes in the prompt", function()
    local path = write("linked.md", "Body.\n")
    write("alpha.md", "See [[linked]] and [[linked]] again.\n")
    open(path)
    answer(2)
    delete.delete()
    assert.is_truthy(asked[1]:find("2 link%(s%) in 1 note%(s%)"))
    assert.is_truthy(asked[1]:find("alpha"))
  end)

  it("counts a link that get_backlinks would miss", function()
    -- A path prefix and a different case: the bracketed-prefix grep in
    -- utils.get_backlinks finds neither, which is why this one resolves exactly.
    local path = write("linked.md", "Body.\n")
    write("bypath.md", "See [[sub/Linked]] here.\n")
    open(path)
    answer(2)
    delete.delete()
    assert.equals(1, #asked)
    assert.is_truthy(asked[1]:find("bypath"))
  end)

  it("ignores a note that only mentions the name outside a link", function()
    local path = write("linked.md", "Body.\n")
    write("prose.md", "linked is discussed but not [[linked-elsewhere]].\n")
    open(path)
    delete.delete()
    assert.equals(0, #asked)
    assert.is_truthy(trashed("linked.md"))
  end)

  it("unwraps the dangling links when asked", function()
    local path = write("linked.md", "Body.\n")
    local other = write("other.md", "Builds on [[linked]] and ![[linked]] and [[linked|the alias]].\n")
    open(path)
    answer(1, 1) -- delete anyway, then unwrap
    delete.delete()
    assert.equals("Builds on linked and linked and the alias.\n", read(other))
  end)

  it("leaves the links alone when the unwrap is declined", function()
    local path = write("linked.md", "Body.\n")
    local other = write("other.md", "Builds on [[linked]].\n")
    open(path)
    answer(1, 2) -- delete anyway, then leave them
    delete.delete()
    assert.equals("Builds on [[linked]].\n", read(other))
    assert.is_truthy(trashed("linked.md"))
  end)

  it("does not touch links to other notes while unwrapping", function()
    local path = write("linked.md", "Body.\n")
    local other = write("other.md", "[[linked]] and [[kept]].\n")
    write("kept.md", "Kept.\n")
    open(path)
    answer(1, 1)
    delete.delete()
    assert.equals("linked and [[kept]].\n", read(other))
  end)

  it("suffixes rather than overwriting a note already in .trash", function()
    write(".trash/dup.md", "The older one.\n")
    local path = write("dup.md", "The newer one.\n")
    open(path)
    delete.delete()
    assert.equals("The older one.\n", trashed("dup.md"))
    assert.equals("The newer one.\n", trashed("dup-1.md"))
  end)

  it("refuses a file outside the vault", function()
    local outside = vim.fn.tempname() .. ".md"
    local f = assert(io.open(outside, "w"))
    f:write("Elsewhere.\n")
    f:close()
    open(outside)
    delete.delete()
    assert.equals(1, vim.fn.filereadable(outside))
    assert.is_truthy(notified[#notified]:find("Not a note in"))
  end)

  it("refuses a note already in .trash", function()
    local path = write(".trash/gone.md", "Already gone.\n")
    open(path)
    delete.delete()
    assert.equals(1, vim.fn.filereadable(path))
    assert.is_truthy(notified[#notified]:find("Already in"))
  end)

  it("refuses a buffer that is not a markdown file", function()
    local path = write("notes.txt", "Not markdown.\n")
    open(path)
    delete.delete()
    assert.equals(1, vim.fn.filereadable(path))
    assert.is_truthy(notified[#notified]:find("Not a markdown file"))
  end)

  -- The soft delete only works because every vault walker skips dot-directories.
  -- Nothing on the Lua side pinned that, and all three walkers used to see
  -- .trash/ -- so a deleted note came back as a random note, as a backlink, and
  -- as a live link blocking the next delete.
  it("is invisible to every vault walker once trashed", function()
    local path = write("gone.md", "Body.\n")
    write("other.md", "Links to [[gone]].\n")
    open(path)
    answer(1, 2) -- delete anyway, leave the links
    delete.delete()

    local listed = table.concat(utils.list_note_files(), " ")
    assert.is_nil(listed:find("gone", 1, true))
    assert.is_nil(utils.find_note_file("gone"))
    -- other.md still says "gone" (the unwrap was declined), so grep legitimately
    -- returns it. What must not come back is the trashed file itself.
    for _, hit in ipairs(utils.grep_note_files("gone")) do
      assert.is_nil(hit:find(".trash", 1, true))
    end
  end)

  it("does not count a link from an already-trashed note", function()
    write(".trash/dead.md", "Dead note linking [[live]].\n")
    local path = write("live.md", "Body.\n")
    open(path)
    delete.delete()
    assert.equals(0, #asked)
    assert.is_truthy(trashed("live.md"))
  end)
end)
