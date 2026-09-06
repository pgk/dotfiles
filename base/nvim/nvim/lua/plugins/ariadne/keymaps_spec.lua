-- Run with :PlenaryBustedFile %, or headless:
--   nvim --headless -c "set rtp+=$HOME/.local/share/nvim/lazy/plenary.nvim" \
--     -c "set rtp+=$PWD/base/nvim/nvim" \
--     -c "PlenaryBustedFile base/nvim/nvim/lua/plugins/ariadne/keymaps_spec.lua"
--
-- Reads init.lua as source rather than loading it: the mappings live inside a
-- lazy.nvim `config` function that needs the real plugin, and what is worth
-- pinning here is textual anyway. similar_spec.lua already does this for the one
-- assertion it needs; this covers the set as a whole, which grew group prefixes
-- (`on*`, `of*`, `ol*`, `og*`) and can now break in two silent ways.
local init = (function()
  local here = debug.getinfo(1, "S").source:sub(2)
  return table.concat(vim.fn.readfile(vim.fn.fnamemodify(here, ":h") .. "/init.lua"), "\n")
end)()

-- { lhs = "<leader>onn", mode = "n" }, in source order.
local function mappings()
  local found = {}
  for mode, lhs in init:gmatch('vim%.keymap%.set%("([nv])",%s*"(<leader>o[a-zA-Z]+)"') do
    table.insert(found, { mode = mode, lhs = lhs })
  end
  return found
end

describe("ariadne keymaps", function()
  it("maps every command exactly once", function()
    local seen = {}
    for _, m in ipairs(mappings()) do
      assert.is_nil(seen[m.lhs], "duplicate mapping: " .. m.lhs)
      seen[m.lhs] = true
    end
  end)

  it("has no mapping that is a prefix of another", function()
    -- A complete mapping that also prefixes a longer one makes nvim wait out
    -- `timeoutlen` before firing it -- a one-second hang on a keystroke that
    -- used to be instant, with nothing on screen to explain it. This is the
    -- failure mode a group prefix introduces, so it is the one to pin.
    local all = mappings()
    for _, a in ipairs(all) do
      for _, b in ipairs(all) do
        if a.lhs ~= b.lhs then
          assert.is_false(
            vim.startswith(b.lhs, a.lhs),
            a.lhs .. " is a prefix of " .. b.lhs
          )
        end
      end
    end
  end)

  it("drives every visual mapping through :<C-u>, never <cmd>", function()
    -- `<cmd>` does not leave Visual mode and nvim writes '< / '> only on exit,
    -- so a `<cmd>` visual mapping reads the PREVIOUS selection -- and nothing at
    -- all on a buffer's first. Both visual commands here read those marks
    -- directly, so this is silent wrongness rather than an error.
    local visual = 0
    for _, m in ipairs(mappings()) do
      if m.mode == "v" then
        visual = visual + 1
        local rhs = init:match(vim.pesc('"' .. m.lhs .. '", "') .. '([^"]*)"')
        assert.is_truthy(rhs, "could not read the rhs of " .. m.lhs)
        assert.is_truthy(vim.startswith(rhs, ":<C-u>"), m.lhs .. " uses " .. rhs)
      end
    end
    assert.equals(2, visual)
  end)

  it("keeps the group prefixes free of complete mappings", function()
    -- The four group letters must stay prefixes only. `<leader>on` firing
    -- something in its own right is what forced this reorganization: it made
    -- every `<leader>on*` wait.
    for _, prefix in ipairs({ "<leader>on", "<leader>of", "<leader>ol", "<leader>og" }) do
      for _, m in ipairs(mappings()) do
        assert.are_not.equal(prefix, m.lhs)
      end
    end
  end)
end)
