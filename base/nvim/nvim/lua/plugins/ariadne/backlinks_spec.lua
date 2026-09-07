-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/backlinks_spec.lua"
--
-- Every vault here is a tempdir. `Obsidian.dir` is set to it so that
-- `utils.vault_path` — and the grep inside it — cannot reach the real vault.
local backlinks = require("plugins.ariadne.backlinks")
local utils = require("plugins.ariadne.utils")

local FIXTURE = vim.fn.fnamemodify(debug.getinfo(1, "S").source:sub(2), ":h") .. "/backlinks-block.fixture"

local vault, notified

local function write(rel, text)
  local path = vault .. "/" .. rel
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  local f = assert(io.open(path, "w"))
  f:write(text)
  f:close()
  return path
end

local function buffer()
  return table.concat(vim.api.nvim_buf_get_lines(0, 0, -1, false), "\n")
end

local BLOCK = table.concat({
  "<!-- ariadne:backlinks -->",
  "## Backlinks",
  "",
  "- [[a-note]]",
  "<!-- /ariadne:backlinks -->",
}, "\n")

describe("backlinks.update", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    notified = {}
    vim.notify = function(msg)
      table.insert(notified, msg)
    end
  end)

  after_each(function()
    _G.Obsidian = nil
  end)

  local function on(rel, text)
    local path = write(rel, text)
    utils.edit(path)
    return path
  end

  it("appends a block naming every note that links here", function()
    write("a-note.md", "See [[current]].\n")
    write("b-note.md", "Also [[current]].\n")
    on("current.md", "The body.\n")
    backlinks.update()
    assert.equals(
      "The body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n- [[b-note]]\n"
        .. "<!-- /ariadne:backlinks -->",
      buffer()
    )
    assert.equals("2 backlinks (+2 a-note, b-note)", notified[1])
  end)

  it("is idempotent — a second run changes nothing", function()
    write("a-note.md", "See [[current]].\n")
    on("current.md", "The body.\n")
    backlinks.update()
    local once = buffer()
    backlinks.update()
    assert.equals(once, buffer())
    assert.equals("1 backlink, unchanged", notified[2])
  end)

  it("keeps a row you annotated, verbatim and in place", function()
    write("a-note.md", "See [[current]].\n")
    write("b-note.md", "Also [[current]].\n")
    on("current.md", "Body.\n\n" .. BLOCK:gsub("%- %[%[a%-note%]%]", "- [[a-note]] — why this one matters") .. "\n")
    backlinks.update()
    assert.equals(
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n"
        .. "- [[a-note]] — why this one matters\n- [[b-note]]\n<!-- /ariadne:backlinks -->",
      buffer()
    )
  end)

  it("keeps an annotation written on its own line under a row", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n"
        .. "  the reason, at length\n<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("- [[a-note]]\n  the reason, at length", 1, true))
  end)

  it("keeps the order you left the rows in, and appends what is new", function()
    write("a-note.md", "See [[current]].\n")
    write("b-note.md", "Also [[current]].\n")
    write("c-note.md", "And [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[c-note]]\n- [[a-note]]\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    -- Plain find, not a pattern: `\n-` reads the hyphen as a lazy quantifier.
    assert.truthy(buffer():find("- [[c-note]]\n- [[a-note]]\n- [[b-note]]", 1, true))
  end)

  it("drops a row whose note stopped linking here, and names it", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n- [[gone-note]] — annotated\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.falsy(buffer():find("gone-note", 1, true))
    assert.equals("1 backlink (-1 gone-note)", notified[1])
  end)

  it("removes the block, and the blank line before it, when nothing links here", function()
    on("current.md", "Body.\n\n" .. BLOCK .. "\n")
    backlinks.update()
    assert.equals("Body.", buffer())
    assert.equals("0 backlinks (-1 a-note)", notified[1])
  end)

  it("writes nothing at all when there are no backlinks and no block", function()
    on("current.md", "Body.\n")
    backlinks.update()
    assert.equals("Body.", buffer())
    assert.equals("0 backlinks, unchanged", notified[1])
  end)

  it("does not read another note's block as a link — the mirror it would cause", function()
    -- b-note's block names current only because current links to b-note. Counting
    -- it would give current a backlink from b-note, then b-note one from current,
    -- and each block would fill up with the notes it links to.
    write("b-note.md", "Body.\n\n<!-- ariadne:backlinks -->\n- [[current]]\n<!-- /ariadne:backlinks -->\n")
    on("current.md", "See [[b-note]].\n")
    backlinks.update()
    assert.equals("See [[b-note]].", buffer())
    assert.equals("0 backlinks, unchanged", notified[1])
  end)

  it("lists a mutual link like any other backlink", function()
    write("a-note.md", "See [[current]].\n")
    on("current.md", "I link back to [[a-note]].\n")
    backlinks.update()
    assert.truthy(buffer():find("- [[a-note]]", 1, true))
  end)

  it("resolves the path, anchor and case forms, and not a merely similar name", function()
    write("a-note.md", "See [[sub/current#Top]].\n")
    write("b-note.md", "See [[CURRENT|the note]].\n")
    write("c-note.md", "See [[current-ideas]] and the word current.\n")
    write("current-ideas.md", "A different note.\n")
    on("current.md", "Body.\n")
    backlinks.update()
    assert.truthy(buffer():find("- [[a-note]]", 1, true))
    assert.truthy(buffer():find("- [[b-note]]", 1, true))
    assert.falsy(buffer():find("c-note", 1, true))
  end)

  it("keeps the body when an unpaired marker sits above the block", function()
    -- The blocker this file exists to pin. Run 1 appends a block, which supplies
    -- the stray marker's missing closer; pairing the FIRST opener with the first
    -- closer then made run 2 replace everything between, deleting the prose and
    -- reporting "unchanged" because the rows had not moved.
    write("a-note.md", "See [[current]].\n")
    on("current.md", "Intro.\n\nA line mentioning\n<!-- ariadne:backlinks -->\nas an example.\n\nMore body here.\n")
    backlinks.update()
    backlinks.update()
    -- Asserted on the stripped text, not the buffer: prose swallowed *into* the
    -- block is just as gone from the graph and the embeddings as prose deleted,
    -- and a buffer-text assertion cannot tell the two apart.
    local authored = backlinks.strip(buffer())
    assert.truthy(authored:find("as an example.", 1, true))
    assert.truthy(authored:find("More body here.", 1, true))
    assert.equals(1, select(2, buffer():gsub("## Backlinks", "")))
  end)

  it("does not read a second block as authored links either", function()
    write(
      "b-note.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n- [[current]]\n<!-- /ariadne:backlinks -->\n"
        .. "\n<!-- ariadne:backlinks -->\n- [[current]]\n<!-- /ariadne:backlinks -->\n"
    )
    on("current.md", "See [[b-note]].\n")
    backlinks.update()
    assert.equals("See [[b-note]].", buffer())
  end)

  it("does not grow a row for a name it cannot write as a link", function()
    -- as_wikilink refuses a bracket, pipe or anchor, so the row is plain text and
    -- has no wikilink to key on. Without a text fallback the old row was absorbed
    -- as an annotation while a fresh one was added, on every single run.
    write("zz-br[ack]et.md", "See [[current]].\n")
    on("current.md", "Body.\n")
    backlinks.update()
    local once = buffer()
    backlinks.update()
    backlinks.update()
    assert.equals(once, buffer())
    assert.equals(1, select(2, buffer():gsub("zz%-br%[ack%]et", "")))
  end)

  it("keeps a #tag annotation, which is not the managed heading", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n  #followup\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("#followup", 1, true))
  end)

  it("keeps a line you wrote above the rows", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\nMost useful first:\n- [[a-note]]\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("Most useful first:", 1, true))
    assert.equals(1, select(2, buffer():gsub("Most useful first:", "")))
  end)

  it("drops a duplicate row without calling it a removed backlink", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]] first\n- [[a-note]]\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.equals(1, select(2, buffer():gsub("%[%[a%-note%]%]", "")))
    assert.equals("1 backlink, unchanged", notified[1])
  end)

  it("does not open an empty note with a blank line", function()
    write("a-note.md", "See [[current]].\n")
    on("current.md", "")
    backlinks.update()
    assert.equals("<!-- ariadne:backlinks -->", vim.api.nvim_buf_get_lines(0, 0, 1, false)[1])
  end)

  it("keeps an annotation on a row it could not write as a link", function()
    -- The name is written in backticks so the row's identity ends where the
    -- annotation begins. Keyed on the whole row text, annotating it changed the
    -- key, so the row was reported removed and rewritten bare.
    write("a#b.md", "See [[current]].\n")
    on("current.md", "Body.\n")
    backlinks.update()
    assert.truthy(buffer():find("- `a#b`", 1, true))
    local annotated = buffer():gsub("%- `a#b`", "- `a#b` — MY ANNOTATION")
    vim.api.nvim_buf_set_lines(0, 0, -1, false, vim.split(annotated, "\n", { plain = true }))
    backlinks.update()
    assert.truthy(buffer():find("- `a#b` — MY ANNOTATION", 1, true))
    assert.equals("1 backlink, unchanged", notified[#notified])
  end)

  it("keeps a blank line inside a multi-paragraph annotation", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n  first para\n\n"
        .. "  second para\n<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("  first para\n\n  second para", 1, true))
  end)

  it("keeps a sub-list written under a row", function()
    -- An indented bullet is the most natural way to annotate a row. Treated as a
    -- row itself it matched no backlink, so it was deleted and reported as two
    -- removed backlinks named "reason one" and "reason two".
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- [[a-note]]\n"
        .. "  - reason one\n  - reason two\n<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("  - reason one\n  - reason two", 1, true))
    assert.equals("1 backlink, unchanged", notified[1])
  end)

  it("keeps a blank line between two paragraphs above the rows", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\nPara one.\n\nPara two.\n"
        .. "- [[a-note]]\n<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("Para one.\n\nPara two.", 1, true))
    assert.equals("1 backlink, unchanged", notified[1])
  end)

  it("does not rewrite a fenced example of a block", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "How it looks:\n\n```\n<!-- ariadne:backlinks -->\n## Backlinks\n\n"
        .. "- [[hub-note]] — an example\n<!-- /ariadne:backlinks -->\n```\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("- [[hub-note]] — an example", 1, true))
    assert.equals("1 backlink (+1 a-note)", notified[1])
  end)

  it("keeps a backticked annotation on an ordinary row", function()
    write("a-note.md", "See [[current]].\n")
    on(
      "current.md",
      "Body.\n\n<!-- ariadne:backlinks -->\n## Backlinks\n\n- `todo` [[a-note]]\n"
        .. "<!-- /ariadne:backlinks -->\n"
    )
    backlinks.update()
    assert.truthy(buffer():find("- `todo` [[a-note]]", 1, true))
    assert.equals("1 backlink, unchanged", notified[1])
  end)

  it("refuses a buffer outside the vault", function()
    utils.edit(vim.fn.tempname() .. ".md")
    backlinks.update()
    assert.truthy(notified[1]:find("Not a note in", 1, true))
  end)
end)

describe("backlinks.span", function()
  it("agrees with the Python walk on what may surround a marker", function()
    -- `vim.trim` is byte-wise ASCII and Python's bare .strip() is the full
    -- Unicode class, so a NBSP here was a block on one side only — the mirror,
    -- live in the editor and invisible to the graph. `ariadne_common_test`
    -- asserts Python refuses this same input.
    local nbsp = "\194\160" .. backlinks.OPEN
    assert.equals(0, #backlinks.spans({ nbsp, "- [[hub]]", backlinks.CLOSE }))
    assert.equals(1, #backlinks.spans({ " \t" .. backlinks.OPEN, "- [[hub]]", backlinks.CLOSE }))
  end)

  it("takes a marker only as the exact text alone on its line", function()
    -- The fixture pins the happy path; only this pins the refusals. Loosening
    -- the Lua walk to a prefix match left all 12 spec files green while
    -- `ariadne_common_test` still refused the same input — the two grammars
    -- drifting apart is a mirror on one side, so every rejection needs the
    -- assertion on both.
    for _, marker in ipairs({ "<!--ariadne:backlinks-->", backlinks.OPEN .. " and more" }) do
      assert.equals(0, #backlinks.spans({ marker, "- [[hub]]", backlinks.CLOSE }))
    end
  end)

  it("ignores markers inside a closed fence, but not an unterminated one", function()
    local block = { backlinks.OPEN, "- [[hub]]", backlinks.CLOSE }
    local quoted = vim.list_extend({ "```" }, vim.list_extend(vim.deepcopy(block), { "```" }))
    assert.equals(0, #backlinks.spans(quoted))
    assert.equals(1, #backlinks.spans(vim.list_extend({ "```" }, vim.deepcopy(block))))
  end)

  it("leaves an unterminated opening marker alone", function()
    local text = "Body.\n<!-- ariadne:backlinks -->\n- [[a]]\n"
    assert.is_nil(backlinks.span(vim.split(text, "\n", { plain = true })))
    assert.equals(text, backlinks.strip(text))
  end)
end)

describe("backlinks.render", function()
  it("reproduces the fixture the Python stripper is pinned against", function()
    -- The two strippers were each pinned by their own hand-written copy of a
    -- block, so neither pinned the other: they disagreed about unspaced markers
    -- and CRLF and both suites stayed green. This file is the one artefact —
    -- `ariadne_common_test.SharedFixtureTests` asserts Python strips exactly it.
    local f = assert(io.open(FIXTURE, "r"))
    local text = f:read("*a")
    f:close()
    local lines = vim.split(text, "\n", { plain = true })
    local first, last = backlinks.span(lines)
    assert.equals(1, first)
    local rows, preamble = backlinks.parse_rows(vim.list_slice(lines, first + 1, last - 1))
    assert.equals(text, table.concat(backlinks.render(rows, preamble), "\n") .. "\n")
  end)
end)

describe("backlinks.linking_notes", function()
  it("reads the context line only when asked for it", function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    write("a-note.md", "See [[current]].\n")
    local path = write("current.md", "Body.\n")
    assert.is_nil(backlinks.linking_notes(path, "current")[1].context)
    assert.equals(
      "See current.",
      backlinks.linking_notes(path, "current", { context = true })[1].context
    )
    _G.Obsidian = nil
  end)
end)

describe("backlinks.context", function()
  it("shows the sentence with the link to this note spelled out", function()
    assert.equals(
      "Compare with a note and [[other]].",
      backlinks.context("intro\nCompare with [[current|a note]] and [[other]].\n", "current")
    )
  end)

  it("says so when the line holds nothing but links", function()
    assert.equals("(link only)", backlinks.context("- [[current]]\n", "current"))
  end)
end)
