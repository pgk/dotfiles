-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/wikilinks_spec.lua"
local wikilinks = require("plugins.ariadne.wikilinks")

describe("wikilinks.key", function()
  it("resolves a plain link to itself, lowercased", function()
    assert.equals("a-note", wikilinks.key("a-note"))
    assert.equals("a-note", wikilinks.key("A-Note"))
  end)

  it("drops a directory prefix, because notes resolve by basename", function()
    assert.equals("a-note", wikilinks.key("dir/sub/a-note"))
    assert.equals("a-note", wikilinks.key([[dir\sub\a-note]]))
  end)

  it("drops a heading anchor", function()
    assert.equals("a-note", wikilinks.key("a-note#Some Heading"))
  end)

  it("ignores the alias, which names nothing", function()
    assert.equals("a-note", wikilinks.key("a-note|Something Else"))
    assert.equals("a-note", wikilinks.key("dir/a-note#Top|Alias"))
  end)

  it("is empty for a link that names no note", function()
    assert.equals("", wikilinks.key("#just-a-heading"))
    assert.equals("", wikilinks.key(""))
  end)

  it("trims surrounding space", function()
    assert.equals("a-note", wikilinks.key("  a-note  "))
  end)
end)

describe("wikilinks.display", function()
  it("prefers the alias", function()
    assert.equals("Something Else", wikilinks.display("a-note|Something Else"))
  end)

  it("falls back to the basename when the alias is blank", function()
    assert.equals("a-note", wikilinks.display("a-note|   "))
  end)

  it("keeps the basename's original case", function()
    assert.equals("A-Note", wikilinks.display("A-Note"))
  end)

  it("shows the note, not the heading, for an anchored link", function()
    assert.equals("a-note", wikilinks.display("a-note#Some Heading"))
  end)

  it("shows the heading when the link names no note", function()
    assert.equals("Some Heading", wikilinks.display("#Some Heading"))
  end)
end)

describe("wikilinks.count_to", function()
  it("counts every form that resolves to the note", function()
    local text = "[[a]] and [[dir/a]] and [[a#Top]] and [[a|Alias]] and ![[a]]"
    assert.equals(5, wikilinks.count_to(text, "a"))
  end)

  it("is case-insensitive on both sides", function()
    assert.equals(2, wikilinks.count_to("[[A-Note]] [[a-note]]", "A-NOTE"))
  end)

  it("does not count a note whose name merely starts the same", function()
    assert.equals(0, wikilinks.count_to("[[a-note-elsewhere]]", "a-note"))
  end)

  it("does not count a bare mention outside a link", function()
    assert.equals(0, wikilinks.count_to("a-note is discussed here", "a-note"))
  end)

  it("does not count an unclosed link", function()
    assert.equals(0, wikilinks.count_to("dangling [[a-note", "a-note"))
  end)
end)

describe("wikilinks.unwrap", function()
  it("replaces the link with the words the reader saw", function()
    local out, n = wikilinks.unwrap("builds on [[a-note]] here", "a-note")
    assert.equals("builds on a-note here", out)
    assert.equals(1, n)
  end)

  it("keeps the alias text", function()
    assert.equals("see the other one", (wikilinks.unwrap("see [[a-note|the other one]]", "a-note")))
  end)

  it("drops the anchor and the directory", function()
    assert.equals("a-note a-note", (wikilinks.unwrap("[[a-note#Top]] [[dir/a-note]]", "a-note")))
  end)

  it("strips the bang from an embed", function()
    assert.equals("a-note", (wikilinks.unwrap("![[a-note]]", "a-note")))
  end)

  it("leaves links to other notes completely alone", function()
    local out, n = wikilinks.unwrap("[[a-note]] and [[b-note]] and [[a-note-elsewhere]]", "a-note")
    assert.equals("a-note and [[b-note]] and [[a-note-elsewhere]]", out)
    assert.equals(1, n)
  end)

  it("reports zero and changes nothing when the note is unlinked", function()
    local text = "no links to it here, only [[something-else]]"
    local out, n = wikilinks.unwrap(text, "a-note")
    assert.equals(text, out)
    assert.equals(0, n)
  end)

  it("leaves an unclosed link alone rather than swallowing the rest", function()
    local text = "dangling [[a-note and then [[a-note]] after"
    assert.equals("dangling [[a-note and then a-note after", (wikilinks.unwrap(text, "a-note")))
  end)

  it("does not treat a percent in the name as a gsub replacement", function()
    -- `%1` in a gsub replacement string is a capture reference; the function
    -- form used here returns it literally, which is what a note name needs.
    local out = wikilinks.unwrap("[[a-note|100%1 sure]]", "a-note")
    assert.equals("100%1 sure", out)
  end)
end)

describe("wikilinks.targets", function()
  it("returns one resolution key per distinct note", function()
    local keys = wikilinks.targets("[[a]] [[dir/a]] [[a#Top]] [[a|Alias]] [[b]]")
    assert.same({ "a", "b" }, keys)
  end)

  it("drops links that name no note", function()
    assert.same({ "a" }, wikilinks.targets("[[#heading]] [[]] [[a]]"))
  end)

  it("is empty for text with no links", function()
    assert.same({}, wikilinks.targets("just prose"))
  end)
end)

describe("wikilinks.retarget", function()
  local function at(text)
    return (wikilinks.retarget(text, "old", "new"))
  end

  it("retargets every form that resolves to the note", function()
    assert.equals("[[new]]", at("[[old]]"))
    assert.equals("[[new]]", at("[[dir/old]]"))
    assert.equals("[[new#Top]]", at("[[old#Top]]"))
    assert.equals("[[new|Alias]]", at("[[old|Alias]]"))
  end)

  it("keeps an embed an embed", function()
    -- Dropping the bang would silently demote a transclusion to a link.
    assert.equals("![[new]]", at("![[old]]"))
  end)

  it("leaves other notes alone", function()
    assert.equals("[[old-elsewhere]] [[other]]", at("[[old-elsewhere]] [[other]]"))
  end)

  it("counts what it rewrote", function()
    local _, n = wikilinks.retarget("[[old]] [[dir/old]] [[other]]", "old", "new")
    assert.equals(2, n)
  end)

  it("refuses a new name that would break out of the link", function()
    -- "]]" in the name would close the link early and forge a different one.
    local out, n = wikilinks.retarget("[[old]]", "old", "ev]]il")
    assert.equals("[[old]]", out)
    assert.equals(0, n)
  end)

  it("refuses a new name carrying link syntax of its own", function()
    for _, bad in ipairs({ "a|b", "a#b", "a[[b" }) do
      assert.equals(0, select(2, wikilinks.retarget("[[old]]", "old", bad)))
    end
  end)
end)
