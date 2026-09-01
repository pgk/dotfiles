-- Ariadne: a Zettelkasten workflow layered on obsidian.nvim.
-- See README.md for the module breakdown.

local vault_path = require("plugins.ariadne.utils").default_vault_path

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
    local utils = require("plugins.ariadne.utils")
    local panel = require("plugins.ariadne.panel")
    local transclusion = require("plugins.ariadne.transclusion")
    local daily = require("plugins.ariadne.daily")
    local commands = require("plugins.ariadne.commands")
    local format = require("plugins.ariadne.format")
    local graph = require("plugins.ariadne.graph")
    local deadlinks = require("plugins.ariadne.deadlinks")
    local similar = require("plugins.ariadne.similar")
    local duplicates = require("plugins.ariadne.duplicates")
    local activity = require("plugins.ariadne.activity")

    -- Setup all modules
    panel.setup()
    transclusion.setup()
    daily.setup()
    commands.setup()
    format.setup()
    graph.setup()
    deadlinks.setup()
    similar.setup()
    duplicates.setup()
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
          vim.opt_local.formatexpr = "v:lua.require'plugins.ariadne.format'.formatexpr()"
        end
        vim.keymap.set("n", "gf", commands.smart_follow_link, { buffer = true, desc = "Smart follow link" })
        vim.keymap.set("n", "<leader>ch", function()
          require("obsidian").util.toggle_checkbox()
        end, { buffer = true, desc = "Toggle checkbox" })
      end,
    })

    -- Global keybindings
    vim.keymap.set("n", "<leader>od", "<cmd>AriadneDaily<cr>", { desc = "Ariadne daily note" })
    vim.keymap.set("n", "<leader>or", "<cmd>AriadneRandom<cr>", { desc = "Ariadne random note" })
    vim.keymap.set("n", "<leader>ol", "<cmd>AriadneLinksPanel<cr>", { desc = "Ariadne links panel" })
    vim.keymap.set("n", "<leader>os", "<cmd>Obsidian search<cr>", { desc = "Ariadne search" })
    vim.keymap.set("n", "<leader>on", "<cmd>Obsidian new<cr>", { desc = "Ariadne new note" })
    vim.keymap.set("n", "<leader>oi", "<cmd>AriadneInsertLink<cr>", { desc = "Ariadne insert link" })
    vim.keymap.set("n", "<leader>ob", function()
      local current_file = vim.api.nvim_buf_get_name(0)
      local backlinks = utils.get_backlinks(current_file)
      if #backlinks == 0 then
        vim.notify("No backlinks found", vim.log.levels.INFO)
        return
      end
      vim.cmd("Obsidian backlinks")
    end, { desc = "Ariadne backlinks (picker)" })
    vim.keymap.set("n", "<leader>of", "<cmd>Obsidian links<cr>", { desc = "Ariadne forward links (picker)" })
    vim.keymap.set("n", "<leader>ot", "<cmd>AriadneTransclusionToggle<cr>", { desc = "Ariadne toggle transclusions" })
    vim.keymap.set("n", "<leader>oR", "<cmd>AriadneRename<cr>", { desc = "Ariadne rename note" })
    vim.keymap.set("v", "<leader>oe", "<cmd>AriadneExtract<cr>", { desc = "Ariadne extract to note" })
    vim.keymap.set("n", "<leader>og", "<cmd>AriadneGraphHealth<cr>", { desc = "Ariadne orphan/sparse/splittable notes" })
    vim.keymap.set("n", "<leader>oD", "<cmd>AriadneDeadLinks<cr>", { desc = "Ariadne dead links" })
    vim.keymap.set("n", "<leader>oS", "<cmd>AriadneSimilar<cr>", { desc = "Ariadne similar unlinked notes" })
    vim.keymap.set("n", "<leader>ou", "<cmd>AriadneDuplicates<cr>", { desc = "Ariadne duplicate notes" })
    vim.keymap.set("n", "<leader>oa", "<cmd>AriadneActive<cr>", { desc = "Ariadne recently active notes" })
    vim.keymap.set("n", "<leader>oh", "<cmd>AriadneHelp<cr>", { desc = "Ariadne help (workflow doc)" })
  end,
  opts = {
    -- Our own commands (AriadneGraphHealth, AriadneActive, ...) are plain user
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
