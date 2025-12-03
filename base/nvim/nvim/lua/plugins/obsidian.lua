return {
  "obsidian-nvim/obsidian.nvim",
  version = "*",
  event = "VeryLazy",
  dependencies = {
    "nvim-lua/plenary.nvim",
  },
  config = function(_, opts)
    require("obsidian").setup(opts)

    -- Random note command
    vim.api.nvim_create_user_command("ObsidianRandom", function()
      local vault_path = vim.fn.expand("~/notes")
      local handle = io.popen('find "' .. vault_path .. '" -name "*.md" -type f')
      if not handle then
        vim.notify("Failed to search vault", vim.log.levels.ERROR)
        return
      end
      local result = handle:read("*a")
      handle:close()

      local files = {}
      for file in result:gmatch("[^\n]+") do
        table.insert(files, file)
      end

      if #files == 0 then
        vim.notify("No notes found in vault", vim.log.levels.WARN)
        return
      end

      math.randomseed(os.time())
      local random_file = files[math.random(#files)]
      vim.cmd("edit " .. vim.fn.fnameescape(random_file))
    end, { desc = "Open a random note from vault" })

    -- Links panel state
    local links_panel = {
      buf = nil,
      win = nil,
      enabled = false,
      autocmd_id = nil,
      current_note = nil, -- Track which note we're showing links for
    }

    local function get_note_name(filepath)
      return vim.fn.fnamemodify(filepath, ":t:r")
    end

    local function get_note_preview(filepath, max_len)
      max_len = max_len or 50
      local file = io.open(filepath, "r")
      if not file then
        return ""
      end
      -- Skip frontmatter and find first meaningful line
      local in_frontmatter = false
      local preview = ""
      for line in file:lines() do
        if line:match("^---") then
          in_frontmatter = not in_frontmatter
        elseif not in_frontmatter then
          -- Skip headings, empty lines, and links-only lines
          local trimmed = line:gsub("^%s+", ""):gsub("%s+$", "")
          if trimmed ~= "" and not trimmed:match("^#") and not trimmed:match("^%[%[.*%]%]$") then
            preview = trimmed
            break
          end
        end
      end
      file:close()
      if #preview > max_len then
        preview = preview:sub(1, max_len) .. "…"
      end
      return preview
    end

    local function get_backlink_context(filepath, note_name, max_len)
      max_len = max_len or 50
      local file = io.open(filepath, "r")
      if not file then
        return ""
      end
      local pattern = "%[%[" .. note_name:gsub("([%-%.%+%[%]%(%)%$%^%%%?%*])", "%%%1")
      for line in file:lines() do
        if line:match(pattern) then
          -- Remove the link itself and clean up
          local context = line:gsub("%[%[[^%]]+%]%]", ""):gsub("^%s+", ""):gsub("%s+$", "")
          file:close()
          if context == "" then
            return "(link only)"
          end
          if #context > max_len then
            context = context:sub(1, max_len) .. "…"
          end
          return context
        end
      end
      file:close()
      return ""
    end

    local function get_forward_links(filepath)
      local vault_path = vim.fn.expand("~/notes")
      local links = {}
      local seen = {}
      local file = io.open(filepath, "r")
      if not file then
        return links
      end
      local content = file:read("*a")
      file:close()

      -- Match [[wiki links]] and [[wiki links|alias]]
      for link in content:gmatch("%[%[([^%]|]+)") do
        if not seen[link] then
          seen[link] = true
          -- Find the actual file path
          local handle = io.popen('find "' .. vault_path .. '" -name "' .. link .. '.md" -type f | head -1')
          if handle then
            local path = handle:read("*a"):gsub("\n", "")
            handle:close()
            if path ~= "" then
              table.insert(links, { name = link, path = path })
            else
              table.insert(links, { name = link, path = nil })
            end
          end
        end
      end

      table.sort(links, function(a, b) return a.name < b.name end)
      return links
    end

    local function get_backlinks(filepath)
      local vault_path = vim.fn.expand("~/notes")
      local note_name = get_note_name(filepath)
      local backlinks = {}

      -- Search for [[note_name using fixed string (matches [[note]] and [[note|alias]])
      local search_term = "[[" .. note_name
      local handle = io.popen('grep -rlF -- "' .. search_term .. '" "' .. vault_path .. '" --include="*.md" 2>/dev/null')
      if not handle then
        return backlinks
      end
      local result = handle:read("*a")
      handle:close()

      for file in result:gmatch("[^\n]+") do
        if file ~= filepath then
          table.insert(backlinks, { name = get_note_name(file), path = file })
        end
      end
      table.sort(backlinks, function(a, b) return a.name < b.name end)
      return backlinks
    end

    local function update_links_panel()
      if not links_panel.buf or not vim.api.nvim_buf_is_valid(links_panel.buf) then
        return
      end
      if not links_panel.win or not vim.api.nvim_win_is_valid(links_panel.win) then
        return
      end

      local current_buf = vim.api.nvim_get_current_buf()

      -- Skip if we're in the panel buffer itself
      if current_buf == links_panel.buf then
        return
      end

      local current_file = vim.api.nvim_buf_get_name(current_buf)

      -- Only update for markdown files in vault
      if not current_file:match("%.md$") or not current_file:match(vim.fn.expand("~/notes")) then
        vim.api.nvim_buf_set_option(links_panel.buf, "modifiable", true)
        vim.api.nvim_buf_set_lines(links_panel.buf, 0, -1, false, { "  Not in vault" })
        vim.api.nvim_buf_set_option(links_panel.buf, "modifiable", false)
        return
      end

      -- Store current note for reference
      links_panel.current_note = current_file

      local forward = get_forward_links(current_file)
      local back = get_backlinks(current_file)
      local current_note_name = get_note_name(current_file)

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
            local preview = get_note_preview(link.path, 40)
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
          local context = get_backlink_context(link.path, current_note_name, 40)
          if context ~= "" then
            table.insert(lines, "    " .. context)
            table.insert(highlights, {#lines - 1, 0, -1, "Comment"})
          end
        end
      end

      vim.api.nvim_buf_set_option(links_panel.buf, "modifiable", true)
      vim.api.nvim_buf_set_lines(links_panel.buf, 0, -1, false, lines)

      -- Apply highlights
      local ns = vim.api.nvim_create_namespace("obsidian_links")
      vim.api.nvim_buf_clear_namespace(links_panel.buf, ns, 0, -1)
      for _, hl in ipairs(highlights) do
        local line, col_start, col_end, group = hl[1], hl[2], hl[3], hl[4]
        if col_end == -1 then
          col_end = #lines[line + 1] or 0
        end
        pcall(vim.api.nvim_buf_add_highlight, links_panel.buf, ns, group, line, col_start, col_end)
      end

      vim.api.nvim_buf_set_option(links_panel.buf, "modifiable", false)
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
      local vault_path = vim.fn.expand("~/notes")
      -- Find the file
      local handle = io.popen('find "' .. vault_path .. '" -name "' .. link .. '.md" -type f | head -1')
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

    local function create_links_panel()
      -- Create buffer
      links_panel.buf = vim.api.nvim_create_buf(false, true)
      vim.api.nvim_buf_set_name(links_panel.buf, "ObsidianLinks")
      vim.api.nvim_buf_set_option(links_panel.buf, "buftype", "nofile")
      vim.api.nvim_buf_set_option(links_panel.buf, "bufhidden", "wipe")
      vim.api.nvim_buf_set_option(links_panel.buf, "swapfile", false)
      vim.api.nvim_buf_set_option(links_panel.buf, "filetype", "ObsidianLinks")

      -- Create window (right side)
      vim.cmd("botright vsplit")
      vim.cmd("vertical resize 35")
      links_panel.win = vim.api.nvim_get_current_win()
      vim.api.nvim_win_set_buf(links_panel.win, links_panel.buf)

      -- Window options
      vim.api.nvim_win_set_option(links_panel.win, "number", false)
      vim.api.nvim_win_set_option(links_panel.win, "relativenumber", false)
      vim.api.nvim_win_set_option(links_panel.win, "signcolumn", "no")
      vim.api.nvim_win_set_option(links_panel.win, "winfixwidth", true)
      vim.api.nvim_win_set_option(links_panel.win, "cursorline", true)

      -- Keymaps for the panel
      local panel_opts = { buffer = links_panel.buf, noremap = true, silent = true }
      vim.keymap.set("n", "<CR>", open_link_under_cursor, panel_opts)
      vim.keymap.set("n", "o", open_link_under_cursor, panel_opts)
      vim.keymap.set("n", "gf", open_link_under_cursor, panel_opts)
      vim.keymap.set("n", "q", function() vim.cmd("ObsidianLinksPanel") end, panel_opts)

      -- Go back to previous window
      vim.cmd("wincmd p")

      -- Set up autocmd to update on buffer change
      links_panel.autocmd_id = vim.api.nvim_create_autocmd({ "BufEnter", "BufWritePost" }, {
        callback = function()
          local current_buf = vim.api.nvim_get_current_buf()
          -- Skip if we're entering the panel buffer itself
          if current_buf == links_panel.buf then
            return
          end
          vim.defer_fn(update_links_panel, 50)
        end,
      })

      links_panel.enabled = true
      update_links_panel()
    end

    local function close_links_panel()
      if links_panel.autocmd_id then
        vim.api.nvim_del_autocmd(links_panel.autocmd_id)
        links_panel.autocmd_id = nil
      end
      if links_panel.win and vim.api.nvim_win_is_valid(links_panel.win) then
        vim.api.nvim_win_close(links_panel.win, true)
      end
      links_panel.buf = nil
      links_panel.win = nil
      links_panel.enabled = false
    end

    vim.api.nvim_create_user_command("ObsidianLinksPanel", function()
      if links_panel.enabled then
        close_links_panel()
      else
        create_links_panel()
      end
    end, { desc = "Toggle Obsidian links panel" })

    -- Add 5 random notes to daily note for review
    vim.api.nvim_create_user_command("ObsidianDailyReview", function()
      local vault_path = vim.fn.expand("~/notes")
      local today = os.date("%Y-%m-%d")
      local daily_note_path = vault_path .. "/" .. today .. ".md"

      -- Get all markdown files
      local handle = io.popen('find "' .. vault_path .. '" -name "*.md" -type f')
      if not handle then
        vim.notify("Failed to search vault", vim.log.levels.ERROR)
        return
      end
      local result = handle:read("*a")
      handle:close()

      -- Get existing links in daily note to avoid duplicates
      local existing_links = {}
      local daily_file_read = io.open(daily_note_path, "r")
      if daily_file_read then
        local content = daily_file_read:read("*a")
        daily_file_read:close()
        for link in content:gmatch("%[%[([^%]|]+)") do
          existing_links[link] = true
        end
      end

      local files = {}
      local today_filename = today .. ".md"
      for file in result:gmatch("[^\n]+") do
        local filename = vim.fn.fnamemodify(file, ":t")
        local note_name = vim.fn.fnamemodify(file, ":t:r")
        -- Exclude today's daily note and already linked notes
        if filename ~= today_filename and not existing_links[note_name] then
          table.insert(files, file)
        end
      end

      if #files < 5 then
        vim.notify("Not enough notes in vault (need at least 5)", vim.log.levels.WARN)
        return
      end

      -- Pick 5 random unique notes
      math.randomseed(os.time())
      local selected = {}
      local indices = {}
      while #selected < 5 do
        local idx = math.random(#files)
        if not indices[idx] then
          indices[idx] = true
          local note_name = vim.fn.fnamemodify(files[idx], ":t:r")
          table.insert(selected, "- [[" .. note_name .. "]]")
        end
      end

      -- Append to daily note
      local daily_file = io.open(daily_note_path, "a")
      if not daily_file then
        vim.notify("Failed to open daily note", vim.log.levels.ERROR)
        return
      end
      daily_file:write("\n## Review\n\n")
      daily_file:write(table.concat(selected, "\n") .. "\n")
      daily_file:close()

      vim.notify("Added 5 random notes to daily review")

      -- Reload if daily note is open
      local current_file = vim.fn.expand("%:p")
      if current_file == daily_note_path then
        vim.cmd("edit!")
      end
    end, { desc = "Add 5 random notes to daily note for review" })

    -- Insert link via fulltext search
    vim.api.nvim_create_user_command("ObsidianInsertLink", function()
      local fzf = require("fzf-lua")
      local vault_path = vim.fn.expand("~/notes")

      fzf.grep({
        cwd = vault_path,
        search = "",
        filespec = "*.md",
        prompt = "Insert link> ",
        actions = {
          ["default"] = function(selected)
            if not selected or #selected == 0 then
              return
            end
            -- Extract filename from selection (format: "file:line:content")
            local file = selected[1]:match("^([^:]+)")
            if file then
              local note_name = vim.fn.fnamemodify(file, ":t:r")
              local link = "[[" .. note_name .. "]]"
              vim.api.nvim_put({ link }, "c", true, true)
            end
          end,
        },
      })
    end, { desc = "Insert link via fulltext search" })

    -- Smart follow link - works even when cursor is on [[ or ]]
    local function smart_follow_link()
      local line = vim.api.nvim_get_current_line()
      local col = vim.api.nvim_win_get_cursor(0)[2] + 1 -- 1-indexed

      -- Find all [[link]] patterns in the line
      for start_pos, link, end_pos in line:gmatch("()%[%[([^%]|]+)[^%]]*%]%]()") do
        -- Check if cursor is anywhere within [[ and ]]
        if col >= start_pos and col <= end_pos - 1 then
          local vault_path = vim.fn.expand("~/notes")
          local handle = io.popen('find "' .. vault_path .. '" -name "' .. link .. '.md" -type f | head -1')
          if handle then
            local result = handle:read("*a"):gsub("\n", "")
            handle:close()
            if result ~= "" then
              vim.cmd("edit " .. vim.fn.fnameescape(result))
              return
            end
          end
          vim.notify("Note not found: " .. link, vim.log.levels.WARN)
          return
        end
      end

      -- Fallback to default gf
      vim.cmd("normal! gf")
    end

    -- Set up path settings and mappings for markdown
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "markdown",
      callback = function()
        vim.opt_local.suffixesadd:append(".md")
        vim.opt_local.path:append(vim.fn.expand("~/notes") .. "/**")
        -- Soft word wrap at window edge
        vim.opt_local.wrap = true
        vim.opt_local.linebreak = true
        vim.opt_local.breakindent = true
        vim.keymap.set("n", "gf", smart_follow_link, { buffer = true, desc = "Smart follow link" })
        vim.keymap.set("n", "<leader>ch", function()
          require("obsidian").util.toggle_checkbox()
        end, { buffer = true, desc = "Toggle checkbox" })
      end,
    })

    -- Keybindings
    vim.keymap.set("n", "<leader>od", "<cmd>ObsidianToday<cr>", { desc = "Obsidian daily note" })
    vim.keymap.set("n", "<leader>or", "<cmd>ObsidianRandom<cr>", { desc = "Obsidian random note" })
    vim.keymap.set("n", "<leader>ol", "<cmd>ObsidianLinksPanel<cr>", { desc = "Obsidian links panel" })
    vim.keymap.set("n", "<leader>os", "<cmd>ObsidianSearch<cr>", { desc = "Obsidian search" })
    vim.keymap.set("n", "<leader>on", "<cmd>ObsidianNew<cr>", { desc = "Obsidian new note" })
    vim.keymap.set("n", "<leader>oi", "<cmd>ObsidianInsertLink<cr>", { desc = "Obsidian insert link" })
  end,
  opts = {
    workspaces = {
      {
        name = "notes",
        path = "~/notes",
      },
    },
    completion = {
      nvim_cmp = false,
      blink = true,
    },
    picker = {
      name = "fzf-lua",
    },
    daily_notes = {
      folder = "",
      date_format = "%Y-%m-%d",
      template = nil,
    },
  },
}
