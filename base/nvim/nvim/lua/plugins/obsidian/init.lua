-- Obsidian integration for Neovim
-- Modular structure:
--   utils.lua       - Shared helper functions
--   panel.lua       - Links panel sidebar
--   transclusion.lua - Transclusion rendering
--   daily.lua       - Daily notes with template
--   commands.lua    - Random, insert link, rename commands

return {
  "obsidian-nvim/obsidian.nvim",
  version = "*",
  event = "VeryLazy",
  dependencies = {
    "nvim-lua/plenary.nvim",
  },
  config = function(_, opts)
    require("obsidian").setup(opts)

    -- Load modules
    local utils = require("plugins.obsidian.utils")
    local panel = require("plugins.obsidian.panel")
    local transclusion = require("plugins.obsidian.transclusion")
    local daily = require("plugins.obsidian.daily")
    local commands = require("plugins.obsidian.commands")

    -- Setup all modules
    panel.setup()
    transclusion.setup()
    daily.setup()
    commands.setup()

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
        vim.opt_local.breakindentopt = "shift:2,sbr"
        vim.opt_local.showbreak = "↳ "
        vim.opt_local.textwidth = 0 -- Don't hard wrap
        vim.keymap.set("n", "gf", commands.smart_follow_link, { buffer = true, desc = "Smart follow link" })
        vim.keymap.set("n", "<leader>ch", function()
          require("obsidian").util.toggle_checkbox()
        end, { buffer = true, desc = "Toggle checkbox" })
      end,
    })

    -- Global keybindings
    vim.keymap.set("n", "<leader>od", "<cmd>ObsidianDaily<cr>", { desc = "Obsidian daily note" })
    vim.keymap.set("n", "<leader>or", "<cmd>ObsidianRandom<cr>", { desc = "Obsidian random note" })
    vim.keymap.set("n", "<leader>ol", "<cmd>ObsidianLinksPanel<cr>", { desc = "Obsidian links panel" })
    vim.keymap.set("n", "<leader>os", "<cmd>ObsidianSearch<cr>", { desc = "Obsidian search" })
    vim.keymap.set("n", "<leader>on", "<cmd>ObsidianNew<cr>", { desc = "Obsidian new note" })
    vim.keymap.set("n", "<leader>oi", "<cmd>ObsidianInsertLink<cr>", { desc = "Obsidian insert link" })
    vim.keymap.set("n", "<leader>ob", function()
      local current_file = vim.api.nvim_buf_get_name(0)
      local backlinks = utils.get_backlinks(current_file)
      if #backlinks == 0 then
        vim.notify("No backlinks found", vim.log.levels.INFO)
        return
      end
      vim.cmd("ObsidianBacklinks")
    end, { desc = "Obsidian backlinks (picker)" })
    vim.keymap.set("n", "<leader>of", "<cmd>ObsidianLinks<cr>", { desc = "Obsidian forward links (picker)" })
    vim.keymap.set("n", "<leader>ot", "<cmd>ObsidianTransclusionToggle<cr>", { desc = "Obsidian toggle transclusions" })
    vim.keymap.set("n", "<leader>oR", "<cmd>ObsidianRename<cr>", { desc = "Obsidian rename note" })
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
