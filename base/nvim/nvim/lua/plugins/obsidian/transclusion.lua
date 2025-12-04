-- Transclusion support for Obsidian integration
local utils = require("plugins.obsidian.utils")

local M = {}

local ns = vim.api.nvim_create_namespace("obsidian_transclusion")
M.enabled = false

-- Define highlight groups
local function setup_highlights()
  vim.api.nvim_set_hl(0, "ObsidianTransclusionBorder", { fg = "#565f89", italic = true })
  vim.api.nvim_set_hl(0, "ObsidianTransclusionContent", { fg = "#9aa5ce", italic = true })
  vim.api.nvim_set_hl(0, "ObsidianTransclusionHeader", { fg = "#7aa2f7", bold = true, italic = true })
  vim.api.nvim_set_hl(0, "ObsidianTransclusionBold", { fg = "#c0caf5", bold = true, italic = true })
  vim.api.nvim_set_hl(0, "ObsidianTransclusionList", { fg = "#9ece6a", italic = true })
  vim.api.nvim_set_hl(0, "ObsidianTransclusionLink", { fg = "#7dcfff", italic = true, underline = true })
end

local function get_content(note_name)
  local handle = io.popen('find "' .. utils.vault_path .. '" -iname "' .. note_name .. '.md" -type f | head -1')
  if not handle then
    return nil
  end
  local filepath = handle:read("*a"):gsub("\n", "")
  handle:close()

  if filepath == "" then
    return nil
  end

  local file = io.open(filepath, "r")
  if not file then
    return nil
  end

  local lines = {}
  local in_frontmatter = false
  local line_num = 0
  for line in file:lines() do
    line_num = line_num + 1
    if line:match("^---") and line_num == 1 then
      in_frontmatter = true
    elseif line:match("^---") and in_frontmatter then
      in_frontmatter = false
    elseif not in_frontmatter then
      table.insert(lines, line)
    end
  end
  file:close()
  return lines
end

function M.render()
  local buf = vim.api.nvim_get_current_buf()
  vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)

  if not M.enabled then
    return
  end

  -- Calculate wrap width based on window width
  local win_width = vim.api.nvim_win_get_width(0)
  local wrap_width = math.max(40, win_width - 10)

  local lines = vim.api.nvim_buf_get_lines(buf, 0, -1, false)
  for i, line in ipairs(lines) do
    -- Match ![[note]] pattern
    local note_name = line:match("!%[%[([^%]|]+)")
    if note_name then
      local content = get_content(note_name)
      if content and #content > 0 then
        local virt_lines = {}
        -- Top border
        table.insert(virt_lines, { { "  ┌─ " .. note_name .. " ", "ObsidianTransclusionBorder" } })
        -- Content lines with wrapping and highlighting
        for _, content_line in ipairs(content) do
          local hl = utils.get_line_highlight(content_line)
          local wrapped = utils.wrap_line(content_line, wrap_width)
          for wi, wline in ipairs(wrapped) do
            local prefix = wi == 1 and "  │ " or "  │   "
            table.insert(virt_lines, { { prefix .. wline, hl } })
          end
        end
        -- Bottom border
        table.insert(virt_lines, { { "  └" .. string.rep("─", 40), "ObsidianTransclusionBorder" } })

        vim.api.nvim_buf_set_extmark(buf, ns, i - 1, 0, {
          virt_lines = virt_lines,
          virt_lines_above = false,
        })
      end
    end
  end
end

function M.toggle()
  M.enabled = not M.enabled
  if M.enabled then
    M.render()
  else
    local buf = vim.api.nvim_get_current_buf()
    vim.api.nvim_buf_clear_namespace(buf, ns, 0, -1)
  end
  vim.notify("Transclusion " .. (M.enabled and "enabled" or "disabled"), vim.log.levels.INFO)
end

function M.debug()
  local output = {}
  table.insert(output, "Vault path: " .. utils.vault_path)
  local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
  for i, line in ipairs(lines) do
    local note_name = line:match("!%[%[([^%]|]+)")
    if note_name then
      table.insert(output, "")
      table.insert(output, "Line " .. i .. ": Found transclusion to '" .. note_name .. "'")
      -- Debug the find command
      local cmd = 'find "' .. utils.vault_path .. '" -iname "' .. note_name .. '.md" -type f'
      table.insert(output, "  Command: " .. cmd)
      local handle = io.popen(cmd .. " 2>&1")
      if handle then
        local result = handle:read("*a")
        handle:close()
        table.insert(output, "  Find result: '" .. result:gsub("\n", " ") .. "'")
      end
      local content = get_content(note_name)
      if content then
        table.insert(output, "  Content: " .. #content .. " lines")
        for j, cl in ipairs(content) do
          table.insert(output, "    [" .. j .. "] " .. cl)
        end
      else
        table.insert(output, "  Content: NOT FOUND")
      end
    end
  end
  -- Open in scratch buffer
  vim.cmd("new")
  vim.api.nvim_buf_set_lines(0, 0, -1, false, output)
  vim.bo.buftype = "nofile"
  vim.bo.bufhidden = "wipe"
end

function M.setup()
  setup_highlights()

  vim.api.nvim_create_user_command("ObsidianTransclusionToggle", function()
    M.toggle()
  end, { desc = "Toggle transclusion rendering" })

  vim.api.nvim_create_user_command("ObsidianTransclusionDebug", function()
    M.debug()
  end, { desc = "Debug transclusion detection" })

  -- Auto-update transclusions on text change
  vim.api.nvim_create_autocmd({ "TextChanged", "TextChangedI", "BufEnter" }, {
    pattern = "*.md",
    callback = function()
      if M.enabled then
        vim.defer_fn(M.render, 100)
      end
    end,
  })
end

return M
