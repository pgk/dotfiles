-- Obsidian integration for Neovim. See README.md for the module breakdown.

local vault_path = require("plugins.obsidian.utils").default_vault_path

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
    local format = require("plugins.obsidian.format")
    local graph = require("plugins.obsidian.graph")
    local deadlinks = require("plugins.obsidian.deadlinks")
    local similar = require("plugins.obsidian.similar")
    local activity = require("plugins.obsidian.activity")

    -- Setup all modules
    panel.setup()
    transclusion.setup()
    daily.setup()
    commands.setup()
    format.setup()
    graph.setup()
    deadlinks.setup()
    similar.setup()
    activity.setup()

    -- Set up path settings and mappings for markdown
    vim.api.nvim_create_autocmd("FileType", {
      pattern = "markdown",
      callback = function()
        vim.opt_local.suffixesadd:append(".md")
        vim.opt_local.path:append(utils.vault_path .. "/**")
        -- Soft word wrap at window edge
        vim.opt_local.wrap = true
        vim.opt_local.linebreak = true
        vim.opt_local.breakindent = true
        vim.opt_local.breakindentopt = "shift:2,sbr"
        vim.opt_local.showbreak = "↳ "
        vim.opt_local.textwidth = 0 -- Don't hard wrap
        local filepath = vim.api.nvim_buf_get_name(0)
        if vim.startswith(filepath, utils.vault_path .. "/") then
          vim.opt_local.formatexpr = "v:lua.require'plugins.obsidian.format'.formatexpr()"
        end
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
    vim.keymap.set("n", "<leader>os", "<cmd>Obsidian search<cr>", { desc = "Obsidian search" })
    vim.keymap.set("n", "<leader>on", "<cmd>Obsidian new<cr>", { desc = "Obsidian new note" })
    vim.keymap.set("n", "<leader>oi", "<cmd>ObsidianInsertLink<cr>", { desc = "Obsidian insert link" })
    vim.keymap.set("n", "<leader>ob", function()
      local current_file = vim.api.nvim_buf_get_name(0)
      local backlinks = utils.get_backlinks(current_file)
      if #backlinks == 0 then
        vim.notify("No backlinks found", vim.log.levels.INFO)
        return
      end
      vim.cmd("Obsidian backlinks")
    end, { desc = "Obsidian backlinks (picker)" })
    vim.keymap.set("n", "<leader>of", "<cmd>Obsidian links<cr>", { desc = "Obsidian forward links (picker)" })
    vim.keymap.set("n", "<leader>ot", "<cmd>ObsidianTransclusionToggle<cr>", { desc = "Obsidian toggle transclusions" })
    vim.keymap.set("n", "<leader>oR", "<cmd>ObsidianRename<cr>", { desc = "Obsidian rename note" })
    vim.keymap.set("v", "<leader>oe", "<cmd>ObsidianExtract<cr>", { desc = "Obsidian extract to note" })
    vim.keymap.set("n", "<leader>og", "<cmd>ObsidianGraphHealth<cr>", { desc = "Obsidian orphan/sparse/splittable notes" })
    vim.keymap.set("n", "<leader>oD", "<cmd>ObsidianDeadLinks<cr>", { desc = "Obsidian dead links" })
    vim.keymap.set("n", "<leader>oS", "<cmd>ObsidianSimilar<cr>", { desc = "Obsidian similar unlinked notes" })
    vim.keymap.set("n", "<leader>oa", "<cmd>ObsidianActive<cr>", { desc = "Obsidian recently active notes" })
    vim.keymap.set("n", "<leader>oh", "<cmd>ObsidianHelp<cr>", { desc = "Obsidian help (workflow doc)" })
  end,
  opts = {
    -- Our own commands (ObsidianGraphHealth, ObsidianActive, ...) are plain user
    -- commands and unaffected; this only drops obsidian.nvim's own ObsidianXxx
    -- aliases, which the four keymaps above were migrated off.
    legacy_commands = false,
    workspaces = {
      {
        name = "notes",
        path = vault_path,
      },
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
