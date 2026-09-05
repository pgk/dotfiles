-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/similar_spec.lua"
--
-- What is pinned here is the argv, which is the whole contract with the CLI --
-- `--from` is what decides the ranking and the payload shape, so dropping it
-- would silently turn a passage query back into a grouped phrase search and
-- still look like it worked. `vim.system` is stubbed and never calls back, so
-- the picker (and fzf-lua) is never reached.
--
-- Every vault is a tempdir with `Obsidian.dir` pointed at it, as delete_spec
-- does, so `utils.vault_path` cannot reach the real vault.
--
-- Note the two path forms in the argv, which is not a bug in the assertions:
-- nvim reports a buffer's name with symlinks resolved (`/private/var/...` on
-- macOS) while `Obsidian.dir` stays as configured (`/var/...`), so the note
-- reaches the CLI resolved and the vault does not. `:AriadneSimilar` has always
-- sent its target the same way. The CLI copes because `resolve_target` falls
-- back to the basename when the absolute path is not one it scanned -- worth
-- knowing, because that fallback is what would pick the wrong note if two notes
-- shared a basename. Passing a resolved vault instead would change the string
-- the embedding cache is keyed on and force a full re-index, so it is left
-- alone deliberately.
local similar = require("plugins.ariadne.similar")

local vault, argv, notes_shown
local real_system, real_notify, real_executable

local function open_note(rel, text)
  local path = vault .. "/" .. rel
  local f = assert(io.open(path, "w"))
  f:write(text)
  f:close()
  vim.cmd.edit({ args = { path } })
  return path
end

local function select_lines(from_line, from_col, to_line, to_col)
  local buf = vim.api.nvim_get_current_buf()
  vim.fn.setpos("'<", { buf, from_line, from_col, 0 })
  vim.fn.setpos("'>", { buf, to_line, to_col, 0 })
end

describe("similar.search_selection", function()
  before_each(function()
    vault = vim.fn.tempname()
    vim.fn.mkdir(vault, "p")
    _G.Obsidian = { dir = vault }
    argv, notes_shown = nil, {}
    real_system, real_notify = vim.system, vim.notify
    real_executable = vim.fn.executable
    vim.fn.executable = function()
      return 1
    end
    vim.system = function(cmd)
      argv = cmd
      return { wait = function() end }
    end
    vim.notify = function(msg)
      table.insert(notes_shown, msg)
    end
  end)

  after_each(function()
    vim.system, vim.notify = real_system, real_notify
    vim.fn.executable = real_executable
    _G.Obsidian = nil
    vim.cmd("silent! %bwipeout!")
  end)

  it("passes an option-shaped selection safely, as --search=TEXT", function()
    open_note("note.md", "---\n")
    select_lines(1, 1, 1, 3)
    similar.search_selection()
    -- A bare `---` would be read as an option and abort the command.
    assert.equals("--search=---", argv[2])
  end)

  it("sends the selected text under --from, with the vault last before --json", function()
    open_note("note.md", "alpha beta\ngamma delta\n")
    select_lines(1, 1, 2, 5)
    similar.search_selection()
    local buffer_path = vim.api.nvim_buf_get_name(0)
    assert.same(
      { "ariadne-similar", "--search=alpha beta\ngamma", "--from", buffer_path, vault, "--json" },
      argv
    )
  end)

  it("passes the buffer's own path as --from, so the note is excluded from its results", function()
    open_note("note.md", "alpha beta gamma delta epsilon\n")
    select_lines(1, 1, 1, 29)
    similar.search_selection()
    local from = nil
    for i, a in ipairs(argv) do
      if a == "--from" then
        from = argv[i + 1]
      end
    end
    assert.equals(vim.api.nvim_buf_get_name(0), from)
    assert.equals("note", vim.fn.fnamemodify(from, ":t:r"))
  end)

  it("refuses a selection that is only whitespace, without running anything", function()
    open_note("note.md", "   \n")
    select_lines(1, 1, 1, 3)
    similar.search_selection()
    assert.is_nil(argv)
    assert.equals("No text selected", notes_shown[1])
  end)

  it("refuses a buffer outside the vault", function()
    local outside = vim.fn.tempname() .. ".md"
    local f = assert(io.open(outside, "w"))
    f:write("some text here\n")
    f:close()
    vim.cmd.edit({ args = { outside } })
    select_lines(1, 1, 1, 9)
    similar.search_selection()
    assert.is_nil(argv)
  end)

  -- The cases above call search_selection() directly, which cannot see how the
  -- command is reached. These two cover that, because `<cmd>` does not leave
  -- Visual mode and nvim only writes '< / '> on exit from it -- so a `<cmd>`
  -- mapping reads the PREVIOUS selection, and reads nothing at all on a
  -- buffer's first selection. Only a test that drives a mapping notices.
  it("through a visual mapping, sends the selection being made right now", function()
    open_note("note.md", "AAAA first line\nBBBB second line\n")
    vim.api.nvim_create_user_command("AriadneSearchSelection", function()
      similar.search_selection()
    end, { range = true })
    vim.keymap.set("v", "<F5>", ":<C-u>AriadneSearchSelection<cr>")

    local function press(keys)
      vim.api.nvim_feedkeys(vim.api.nvim_replace_termcodes(keys, true, false, true), "x", false)
    end
    press("ggV<Esc>") -- an earlier, different selection: stale marks would show it
    press("jV<F5>")

    assert.is_not_nil(argv)
    assert.equals("--search=BBBB second line", argv[2])

    vim.keymap.del("v", "<F5>")
    vim.api.nvim_del_user_command("AriadneSearchSelection")
  end)

  it("is mapped in init.lua as :<C-u>, never as <cmd>", function()
    -- The shape above is only correct if the real keymap uses it. Reading the
    -- source is crude, but it is what stands between a one-character edit and
    -- silently querying the wrong paragraph.
    local here = debug.getinfo(1, "S").source:sub(2)
    local init = vim.fn.fnamemodify(here, ":h") .. "/init.lua"
    local text = table.concat(vim.fn.readfile(init), "\n")
    assert.is_truthy(text:find(":<C-u>AriadneSearchSelection<cr>", 1, true))
    assert.is_nil(text:find("<cmd>AriadneSearchSelection", 1, true))
    -- AriadneExtract reads the same marks through the same helper.
    assert.is_nil(text:find("<cmd>AriadneExtract", 1, true))
  end)

  -- These two drive the callback all the way into the picker, which no other
  -- case does. The `passage` field is emitted for EVERY query now, so a
  -- whole-note result carries JSON null -- and `vim.json.decode` maps null to
  -- `vim.NIL`, which is truthy userdata that `vim.trim` throws on. One guard in
  -- open_picker is all that keeps plain :AriadneSimilar working.
  local function reply(payload)
    local real_schedule = vim.schedule
    local captured
    package.loaded["fzf-lua"] = { fzf_exec = function(lines, opts) captured = opts end }
    vim.schedule = function(f) f() end
    vim.system = function(_, _, cb)
      cb({ stdout = payload, code = 0, stderr = "" })
    end
    open_note("note.md", "alpha beta\ngamma delta\n")
    select_lines(1, 1, 2, 5)
    similar.search_selection()
    vim.schedule = real_schedule
    package.loaded["fzf-lua"] = nil
    return captured
  end

  local ROW = '{"name":"other","path":"/v/other.md","score":0.5,"linked":false,'
    .. '"crosses":false,"cluster":1,"preview":"p"}'

  it("renders a whole-note payload whose passage is JSON null", function()
    local opts = reply('{"available":true,"error":null,"shape":null,"passage":null,'
      .. '"target":{"name":"note","path":"/v/note.md"},"similar":[' .. ROW .. "]}")
    assert.is_not_nil(opts)
    assert.is_nil(opts.fzf_opts)
  end)

  it("collapses a multi-line passage into the header instead of escaping it", function()
    local opts = reply('{"available":true,"error":null,"shape":null,'
      .. '"passage":"alpha beta\\ngamma delta\\n\\tepsilon",'
      .. '"target":{"name":"note","path":"/v/note.md"},"similar":[' .. ROW .. "]}")
    assert.is_not_nil(opts.fzf_opts)
    assert.equals("passage: alpha beta gamma delta epsilon", opts.fzf_opts["--header"])
  end)

  it("a whole-note query sends no --search and no --from", function()
    open_note("note.md", "alpha beta\n")
    similar.find_similar()
    assert.same({ "ariadne-similar", vim.api.nvim_buf_get_name(0), vault, "--json" }, argv)
  end)
end)
