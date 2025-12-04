-- Links panel for Obsidian integration
local utils = require("plugins.obsidian.utils")

local M = {}

-- Panel state
M.state = {
  buf = nil,
  win = nil,
  enabled = false,
  autocmd_id = nil,
  current_note = nil,
}

local function update_panel()
  if not M.state.buf or not vim.api.nvim_buf_is_valid(M.state.buf) then
    return
  end
  if not M.state.win or not vim.api.nvim_win_is_valid(M.state.win) then
    return
  end

  local current_buf = vim.api.nvim_get_current_buf()

  -- Skip if we're in the panel buffer itself
  if current_buf == M.state.buf then
    return
  end

  local current_file = vim.api.nvim_buf_get_name(current_buf)

  -- Only update for markdown files in vault
  if not current_file:match("%.md$") or not current_file:match(vim.fn.expand("~/notes")) then
    vim.api.nvim_buf_set_option(M.state.buf, "modifiable", true)
    vim.api.nvim_buf_set_lines(M.state.buf, 0, -1, false, { "  Not in vault" })
    vim.api.nvim_buf_set_option(M.state.buf, "modifiable", false)
    return
  end

  -- Store current note for reference
  M.state.current_note = current_file

  local forward = utils.get_forward_links(current_file)
  local back = utils.get_backlinks(current_file)
  local current_note_name = utils.get_note_name(current_file)

  local lines = {}
  local highlights = {} -- {line, col_start, col_end, hl_group}

  table.insert(lines, " " .. current_note_name)
  table.insert(highlights, {#lines - 1, 1, 1 + #current_note_name, "Title"})
  table.insert(lines, "")
  table.insert(lines, " Forward Links (" .. #forward .. ")")
  table.insert(highlights, {#lines - 1, 0, -1, "Comment"})
  table.insert(lines, string.rep("─", 30))
  if #forward == 0 then
    table.insert(lines, "  (none)")
  else
    for _, link in ipairs(forward) do
      local line_num = #lines
      table.insert(lines, "  " .. link.name)
      table.insert(highlights, {line_num, 2, 2 + #link.name, "Function"})
      -- Add preview on next line
      if link.path then
        local preview = utils.get_note_preview(link.path, 40)
        if preview ~= "" then
          table.insert(lines, "    " .. preview)
          table.insert(highlights, {#lines - 1, 0, -1, "Comment"})
        end
      end
    end
  end
  table.insert(lines, "")
  table.insert(lines, " Backlinks (" .. #back .. ")")
  table.insert(highlights, {#lines - 1, 0, -1, "Comment"})
  table.insert(lines, string.rep("─", 30))
  if #back == 0 then
    table.insert(lines, "  (none)")
  else
    for _, link in ipairs(back) do
      local line_num = #lines
      table.insert(lines, "  " .. link.name)
      table.insert(highlights, {line_num, 2, 2 + #link.name, "Function"})
      -- Add context (the line where link appears)
      local context = utils.get_backlink_context(link.path, current_note_name, 40)
      if context ~= "" then
        table.insert(lines, "    " .. context)
        table.insert(highlights, {#lines - 1, 0, -1, "Comment"})
      end
    end
  end

  vim.api.nvim_buf_set_option(M.state.buf, "modifiable", true)
  vim.api.nvim_buf_set_lines(M.state.buf, 0, -1, false, lines)

  -- Apply highlights
  local ns = vim.api.nvim_create_namespace("obsidian_links")
  vim.api.nvim_buf_clear_namespace(M.state.buf, ns, 0, -1)
  for _, hl in ipairs(highlights) do
    local line, col_start, col_end, group = hl[1], hl[2], hl[3], hl[4]
    if col_end == -1 then
      col_end = #lines[line + 1] or 0
    end
    pcall(vim.api.nvim_buf_add_highlight, M.state.buf, ns, group, line, col_start, col_end)
  end

  vim.api.nvim_buf_set_option(M.state.buf, "modifiable", false)
end

local function open_link_under_cursor()
  local line = vim.api.nvim_get_current_line()
  -- Skip headers, separators, empty lines, "(none)", and preview lines (4+ spaces)
  if line:match("^%s*$") or line:match("─") or line:match("Forward Links") or line:match("Backlinks") or line:match("%(none%)") or line:match("Not in vault") or line:match("^%s%s%s%s") then
    return
  end
  -- Link lines have exactly 2 spaces prefix
  if not line:match("^  %S") then
    return
  end
  -- Extract note name (strip the 2 leading spaces)
  local link = line:sub(3)
  if link == "" then
    return
  end
  -- Find the file
  local handle = io.popen('find "' .. utils.vault_path .. '" -iname "' .. link .. '.md" -type f | head -1')
  if not handle then
    return
  end
  local result = handle:read("*a"):gsub("\n", "")
  handle:close()
  if result ~= "" then
    -- Focus previous window and open file
    vim.cmd("wincmd p")
    vim.cmd("edit " .. vim.fn.fnameescape(result))
  else
    vim.notify("Note not found: " .. link, vim.log.levels.WARN)
  end
end

function M.create()
  -- Create buffer
  M.state.buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_name(M.state.buf, "ObsidianLinks")
  vim.api.nvim_buf_set_option(M.state.buf, "buftype", "nofile")
  vim.api.nvim_buf_set_option(M.state.buf, "bufhidden", "wipe")
  vim.api.nvim_buf_set_option(M.state.buf, "swapfile", false)
  vim.api.nvim_buf_set_option(M.state.buf, "filetype", "ObsidianLinks")

  -- Create window (right side)
  vim.cmd("botright vsplit")
  vim.cmd("vertical resize 35")
  M.state.win = vim.api.nvim_get_current_win()
  vim.api.nvim_win_set_buf(M.state.win, M.state.buf)

  -- Window options
  vim.api.nvim_win_set_option(M.state.win, "number", false)
  vim.api.nvim_win_set_option(M.state.win, "relativenumber", false)
  vim.api.nvim_win_set_option(M.state.win, "signcolumn", "no")
  vim.api.nvim_win_set_option(M.state.win, "winfixwidth", true)
  vim.api.nvim_win_set_option(M.state.win, "cursorline", true)

  -- Keymaps for the panel
  local panel_opts = { buffer = M.state.buf, noremap = true, silent = true }
  vim.keymap.set("n", "<CR>", open_link_under_cursor, panel_opts)
  vim.keymap.set("n", "o", open_link_under_cursor, panel_opts)
  vim.keymap.set("n", "gf", open_link_under_cursor, panel_opts)
  vim.keymap.set("n", "q", function() M.toggle() end, panel_opts)

  -- Go back to previous window
  vim.cmd("wincmd p")

  -- Set up autocmd to update on buffer change
  M.state.autocmd_id = vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost" }, {
    callback = function()
      local current_buf = vim.api.nvim_get_current_buf()
      -- Skip if we're entering the panel buffer itself
      if current_buf == M.state.buf then
        return
      end
      vim.defer_fn(update_panel, 50)
    end,
  })

  M.state.enabled = true
  update_panel()
end

function M.close()
  if M.state.autocmd_id then
    vim.api.nvim_del_autocmd(M.state.autocmd_id)
    M.state.autocmd_id = nil
  end
  if M.state.win and vim.api.nvim_win_is_valid(M.state.win) then
    vim.api.nvim_win_close(M.state.win, true)
  end
  M.state.buf = nil
  M.state.win = nil
  M.state.enabled = false
end

function M.toggle()
  if M.state.enabled then
    M.close()
  else
    M.create()
  end
end

function M.setup()
  vim.api.nvim_create_user_command("ObsidianLinksPanel", function()
    M.toggle()
  end, { desc = "Toggle Obsidian links panel" })
end

return M
