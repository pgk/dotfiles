-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/folgezettel_spec.lua"
local fz = require("plugins.ariadne.folgezettel")

describe("folgezettel.segments", function()
  it("splits an alternating id", function()
    assert.same({ "1" }, fz.segments("1"))
    assert.same({ "1", "a" }, fz.segments("1a"))
    assert.same({ "1", "a", "1" }, fz.segments("1a1"))
    assert.same({ "12", "ab", "34" }, fz.segments("12ab34"))
  end)

  it("rejects anything that is not a clean alternation", function()
    for _, bad in ipairs({ "a1", "1-a", "1a-2", "1a ", " 1a", "1_a", "", "1A" }) do
      assert.is_nil(fz.segments(bad), bad)
    end
  end)

  it("rejects a non-string", function()
    assert.is_nil(fz.segments(nil))
    assert.is_nil(fz.segments(12))
  end)
end)

describe("folgezettel.split", function()
  it("separates the id from the title", function()
    assert.same({ "1a", "Note title" }, { fz.split("1a Note title") })
    assert.same({ "1a1", "Working memory limits" }, { fz.split("1a1 Working memory limits") })
  end)

  it("accepts an id with no title", function()
    assert.same({ "7", "" }, { fz.split("7") })
  end)

  it("keeps the title verbatim, punctuation and all", function()
    assert.same({ "1a", "Simon's rule: a note, or two" }, { fz.split("1a Simon's rule: a note, or two") })
  end)

  it("returns nil for a note outside the scheme", function()
    for _, stem in ipairs({ "hub-note", "meeting notes", "1a-2 x", "" }) do
      assert.is_nil(fz.split(stem), stem)
    end
  end)
end)

describe("folgezettel.child", function()
  it("appends a segment of the opposite kind", function()
    assert.equals("1a", fz.child("1"))
    assert.equals("1a1", fz.child("1a"))
    assert.equals("1a1a", fz.child("1a1"))
    assert.equals("1a1a1", fz.child("1a1a"))
  end)

  it("is nil for a malformed id", function()
    assert.is_nil(fz.child("nope"))
  end)
end)

describe("folgezettel.sibling", function()
  it("increments the last segment", function()
    assert.equals("2", fz.sibling("1"))
    assert.equals("1b", fz.sibling("1a"))
    assert.equals("1a2", fz.sibling("1a1"))
  end)

  it("carries digits past nine", function()
    assert.equals("10", fz.sibling("9"))
    assert.equals("1a10", fz.sibling("1a9"))
    assert.equals("100", fz.sibling("99"))
  end)

  it("carries letters past z, bijectively", function()
    assert.equals("1aa", fz.sibling("1z"))
    assert.equals("1ba", fz.sibling("1az"))
    assert.equals("1aaa", fz.sibling("1zz"))
  end)

  it("leaves the earlier segments untouched when carrying", function()
    assert.equals("1a1aa", fz.sibling("1a1z"))
  end)

  it("is nil for a malformed id", function()
    assert.is_nil(fz.sibling("nope"))
  end)
end)

describe("folgezettel.first_free", function()
  it("returns the start when nothing is taken", function()
    assert.equals("1a1", fz.first_free("1a1", {}))
  end)

  it("walks forward past taken ids", function()
    assert.equals("1a3", fz.first_free("1a1", { ["1a1"] = true, ["1a2"] = true }))
    assert.equals("1c", fz.first_free("1b", { ["1b"] = true }))
  end)

  it("compares case-insensitively", function()
    -- Taken ids are lowercased by the caller; the candidate must match that.
    assert.equals("1b", fz.first_free("1a", { ["1a"] = true }))
  end)

  it("walks across a carry", function()
    local taken = {}
    for c in ("xyz"):gmatch(".") do
      taken["1" .. c] = true
    end
    assert.equals("1aa", fz.first_free("1x", taken))
  end)
end)
