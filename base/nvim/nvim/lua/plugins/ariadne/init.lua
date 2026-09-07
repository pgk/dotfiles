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
    local search = require("plugins.ariadne.search")
    local duplicates = require("plugins.ariadne.duplicates")
    local delete = require("plugins.ariadne.delete")
    local branch = require("plugins.ariadne.branch")
    local place = require("plugins.ariadne.place")
    local activity = require("plugins.ariadne.activity")
    local backlinks = require("plugins.ariadne.backlinks")

    -- Setup all modules
    panel.setup()
    transclusion.setup()
    daily.setup()
    commands.setup()
    format.setup()
    graph.setup()
    deadlinks.setup()
    similar.setup()
    search.setup()
    duplicates.setup()
    delete.setup()
    branch.setup()
    place.setup()
    activity.setup()
    backlinks.setup()

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
        if utils.in_vault(filepath) then
          vim.opt_local.formatexpr = "v:lua.require'plugins.ariadne.format'.formatexpr()"
        end
        vim.keymap.set("n", "gf", commands.smart_follow_link, { buffer = true, desc = "Smart follow link" })
        vim.keymap.set("n", "<leader>ch", function()
          require("obsidian").util.toggle_checkbox()
        end, { buffer = true, desc = "Toggle checkbox" })
      end,
    })

    -- Global keybindings, grouped by what you are trying to do: `n`ew, `f`ind,
    -- `l`inks (this note's edges) and `g`raph (the whole vault). The group letter
    -- is an insertion rather than a replacement -- `ol` -> `oll`, `oD` -> `ogd`,
    -- `ou` -> `ogu` -- so the keystroke that carries the meaning is mostly the
    -- one it always was. What the grouping is actually for is retiring the
    -- case-sensitive pairs (`os`/`oS`, `oq`/`oQ`, `ob`/`oB`, `od`/`oD`), where the
    -- shift key was doing the work of a namespace.

    -- n: bring a note into existence.
    vim.keymap.set("n", "<leader>onn", "<cmd>Obsidian new<cr>", { desc = "Ariadne new note" })
    vim.keymap.set("n", "<leader>ond", "<cmd>AriadneDaily<cr>", { desc = "Ariadne daily note" })
    vim.keymap.set("n", "<leader>onb", "<cmd>AriadneBranch<cr>", { desc = "Ariadne branch note (1a -> 1a1)" })
    vim.keymap.set("n", "<leader>ons", "<cmd>AriadneSibling<cr>", { desc = "Ariadne sibling note (1a -> 1b)" })
    vim.keymap.set("n", "<leader>onp", "<cmd>AriadnePlace<cr>", { desc = "Ariadne place note in the hierarchy" })
    -- Same `:<C-u>` reason as <leader>ofp below. This one was a pre-existing bug:
    -- as a `<cmd>` mapping it extracted the previously selected text into the
    -- new note, and refused outright on a buffer's first selection.
    vim.keymap.set("v", "<leader>one", ":<C-u>AriadneExtract<cr>", { desc = "Ariadne extract to note" })

    -- f: find a note.
    vim.keymap.set("n", "<leader>off", "<cmd>Obsidian search<cr>", { desc = "Ariadne search (fulltext)" })
    vim.keymap.set("n", "<leader>ofq", "<cmd>AriadneSearch<cr>", { desc = "Ariadne semantic search" })
    -- `:<C-u>` and not `<cmd>`: `<cmd>` does not leave Visual mode, and nvim only
    -- writes the '< / '> marks on exit from it -- so a `<cmd>` mapping reads the
    -- PREVIOUS selection, and reads nothing at all the first time a buffer is
    -- selected in. Verified: with line 2 selected, a `<cmd>`-fired command sees
    -- line 1. The `<C-u>` clears the '<,'> range nvim inserts for us, which this
    -- command does not use -- it reads the marks itself, to keep the columns.
    vim.keymap.set("v", "<leader>ofp", ":<C-u>AriadneSearchSelection<cr>", { desc = "Ariadne similar to selection" })
    vim.keymap.set("n", "<leader>ofs", "<cmd>AriadneSimilar<cr>", { desc = "Ariadne similar unlinked notes" })
    vim.keymap.set("n", "<leader>ofr", "<cmd>AriadneRandom<cr>", { desc = "Ariadne random note" })

    -- l: this note's own edges.
    vim.keymap.set("n", "<leader>oll", "<cmd>AriadneLinksPanel<cr>", { desc = "Ariadne links panel" })
    vim.keymap.set("n", "<leader>olb", function()
      local current_file = vim.api.nvim_buf_get_name(0)
      local linked = backlinks.linking_notes(utils.resolve(current_file), utils.get_note_name(current_file))
      if #linked == 0 then
        vim.notify("No backlinks found", vim.log.levels.INFO)
        return
      end
      vim.cmd("Obsidian backlinks")
    end, { desc = "Ariadne backlinks (picker)" })
    vim.keymap.set("n", "<leader>olf", "<cmd>Obsidian links<cr>", { desc = "Ariadne forward links (picker)" })
    vim.keymap.set("n", "<leader>oli", "<cmd>AriadneInsertLink<cr>", { desc = "Ariadne insert link" })
    vim.keymap.set("n", "<leader>olt", "<cmd>AriadneTransclusionToggle<cr>", { desc = "Ariadne toggle transclusions" })
    vim.keymap.set("n", "<leader>olw", "<cmd>AriadneBacklinks<cr>", { desc = "Ariadne write backlinks into the note" })

    -- g: the whole vault, not the note in front of you.
    vim.keymap.set("n", "<leader>ogg", "<cmd>AriadneGraphHealth<cr>", { desc = "Ariadne orphan/sparse/splittable notes" })
    vim.keymap.set("n", "<leader>ogd", "<cmd>AriadneDeadLinks<cr>", { desc = "Ariadne dead links" })
    vim.keymap.set("n", "<leader>ogu", "<cmd>AriadneDuplicates<cr>", { desc = "Ariadne duplicate notes" })
    vim.keymap.set("n", "<leader>oga", "<cmd>AriadneActive<cr>", { desc = "Ariadne recently active notes" })

    -- Flat, and deliberately so: the two irreversible ones sit off the group
    -- prefixes, where a slip inside a group cannot reach them, and help is meta.
    vim.keymap.set("n", "<leader>oR", "<cmd>AriadneRename<cr>", { desc = "Ariadne rename note" })
    vim.keymap.set("n", "<leader>oX", "<cmd>AriadneDelete<cr>", { desc = "Ariadne delete note (to .trash/)" })
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
