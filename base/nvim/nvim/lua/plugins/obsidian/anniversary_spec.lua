-- Tests for the "on this day" date logic. Run with:
--   :PlenaryBustedFile %
--   nvim --headless -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/obsidian/anniversary_spec.lua"
--
-- date_from_name and on_this_day are pure; entries_for reads the filesystem and
-- gets a tempdir of its own.
local anniversary = require("plugins.obsidian.anniversary")

describe("anniversary.date_from_name", function()
  it("reads a daily note filename", function()
    assert.equals("2025-09-01", anniversary.date_from_name("2025-09-01"))
  end)

  it("reads a dated prefix followed by a title", function()
    assert.equals("2024-03-05", anniversary.date_from_name("2024-03-05-harbour-metaphor"))
    assert.equals("2024-03-05", anniversary.date_from_name("2024-03-05 harbour metaphor"))
  end)

  it("reads the 00YYYYMMDD-N names the old mknote script wrote", function()
    -- No other pattern matches this form, so it needs its own: read as a bare
    -- YYYYMMDD the stem has a digit where the separator belongs.
    assert.is_nil(("0020240305-7"):match("^(%d%d%d%d)(%d%d)(%d%d)[%-_ ]"))
    assert.equals("2024-03-05", anniversary.date_from_name("0020240305-7"))
  end)

  it("reads a compact date, with or without a title after it", function()
    assert.equals("2024-03-05", anniversary.date_from_name("20240305-harbour"))
    assert.equals("2024-03-05", anniversary.date_from_name("20240305"))
  end)

  it("rejects a number that is not a date", function()
    assert.is_nil(anniversary.date_from_name("12345678-x"))
    assert.is_nil(anniversary.date_from_name("2024-13-05"))
    assert.is_nil(anniversary.date_from_name("2024-00-05"))
    assert.is_nil(anniversary.date_from_name("2024-03-32"))
  end)

  it("rejects a name that merely contains a date", function()
    assert.is_nil(anniversary.date_from_name("notes-on-2024-03-05"))
  end)

  it("rejects an undated name without throwing", function()
    assert.is_nil(anniversary.date_from_name("harbour-metaphor"))
    assert.is_nil(anniversary.date_from_name(""))
    assert.is_nil(anniversary.date_from_name(nil))
  end)
end)

describe("anniversary.on_this_day", function()
  local function entry(name, name_date, mtime_date)
    return { name = name, path = "/v/" .. name .. ".md", name_date = name_date, mtime_date = mtime_date }
  end

  it("matches the same day in an earlier year", function()
    local hits = anniversary.on_this_day({ entry("2025-09-01", "2025-09-01") }, "2026-09-01")
    assert.equals(1, #hits)
    assert.equals("2025-09-01", hits[1].name)
    assert.equals(1, hits[1].years_ago)
  end)

  it("ignores a different day and the current year", function()
    local hits = anniversary.on_this_day({
      entry("2025-09-02", "2025-09-02"),
      entry("2026-09-01", "2026-09-01"),
    }, "2026-09-01")
    assert.equals(0, #hits)
  end)

  it("matches on modification date when the name carries none", function()
    local hits = anniversary.on_this_day({ entry("harbour", nil, "2023-09-01") }, "2026-09-01")
    assert.equals(1, #hits)
    assert.equals(3, hits[1].years_ago)
    assert.equals("mtime", hits[1].source)
  end)

  it("prefers the name date when a note has both", function()
    local hits = anniversary.on_this_day({ entry("2024-09-01", "2024-09-01", "2025-09-01") }, "2026-09-01")
    assert.equals(1, #hits)
    assert.equals("name", hits[1].source)
    assert.equals(2, hits[1].years_ago)
  end)

  it("does not fall back to mtime when the name carries a date that misses", function()
    -- Otherwise a note named 2024-09-15 is listed on September 1st, over a row
    -- whose own filename contradicts the date beside it.
    local hits = anniversary.on_this_day({ entry("harbour", "2024-09-15", "2023-09-01") }, "2026-09-01")
    assert.equals(0, #hits)
  end)

  it("puts the most recent year first", function()
    local hits = anniversary.on_this_day({
      entry("old", "2020-09-01"),
      entry("recent", "2025-09-01"),
      entry("middle", "2023-09-01"),
    }, "2026-09-01")
    assert.same({ "recent", "middle", "old" }, { hits[1].name, hits[2].name, hits[3].name })
  end)

  it("keeps a leap-day note invisible in a non-leap year", function()
    -- February 29th has no anniversary in 2025, and neither neighbouring day is
    -- claimed as one. Documenting the behaviour, not endorsing it.
    local leap = { entry("2024-02-29", "2024-02-29") }
    assert.equals(0, #anniversary.on_this_day(leap, "2025-02-28"))
    assert.equals(0, #anniversary.on_this_day(leap, "2025-03-01"))
    assert.equals(1, #anniversary.on_this_day(leap, "2028-02-29"))
  end)

  it("returns nothing for an empty vault", function()
    assert.same({}, anniversary.on_this_day({}, "2026-09-01"))
  end)
end)

describe("anniversary.entries_for", function()
  local vault, dated, undated

  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    dated = vault .. "/2024-03-05-harbour.md"
    undated = vault .. "/harbour-metaphor.md"
    vim.fn.writefile({ "note" }, dated)
    vim.fn.writefile({ "note" }, undated)
  end)

  after_each(function()
    vim.fn.delete(vault, "rf")
  end)

  it("reads a date out of the name and an mtime out of every file", function()
    local entries = anniversary.entries_for({ dated, undated }, vault)
    assert.equals(2, #entries)
    local by_name = {}
    for _, e in ipairs(entries) do
      by_name[e.name] = e
    end
    assert.equals("2024-03-05", by_name["2024-03-05-harbour"].name_date)
    assert.is_nil(by_name["harbour-metaphor"].name_date)
    for _, e in ipairs(entries) do
      assert.truthy(e.mtime_date:match("^%d%d%d%d%-%d%d%-%d%d$"))
    end
  end)

  it("refuses to stat a path outside the vault", function()
    -- list_note_files splits find(1) output on newlines, so a note named
    -- "x\n/etc/hosts" yields a second path that was never a note.
    local entries = anniversary.entries_for({ dated, "/etc/hosts" }, vault)
    assert.equals(1, #entries)
    assert.equals("2024-03-05-harbour", entries[1].name)
  end)

  it("skips a path that does not exist", function()
    assert.same({}, anniversary.entries_for({ vault .. "/gone.md" }, vault))
  end)
end)
