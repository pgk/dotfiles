# read theme pref from file.
-- local function read_theme_pref()
--   local file = io.open("~/.nvim-colorscheme.txt", "r")
--   if not file then
--     return "dark"
--   end
--   local content = file:read("*a")
--   file:close()
--   vim.notify("Hello from Neovim", vim.log.levels.INFO)
--   return content:match("^%s*(.-)%s*$")
-- end
--
-- local theme_pref = read_theme_pref()
-- local colorscheme = "tokyonight-moon"
-- if theme_pref and theme_pref:match("^light") then
--   colorscheme = "tokyonight-day"
-- else
--   colorscheme = "tokyonight"
-- end


return {
  {
    "folke/tokyonight.nvim",
    lazy = true,
    opts = { style = "moon" },
  },
  {
    "LazyVim/LazyVim",
    opts = {
      colorscheme = "tokyonight-moon",
    },
  },
}
