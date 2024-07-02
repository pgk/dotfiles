lua <<EOF
require('gpt').setup({
      api_key = os.getenv("OPENAI_API_KEY")
    })

    opts = { silent = true, noremap = true }
    vim.keymap.set('v', '<leader>gpr', function () require('gpt').replace(opts) end, {
      silent = true,
      noremap = true,
      desc = "[G]pt [R]ewrite"
    })
    vim.keymap.set('v', '<leader>gpp', function () require('gpt').visual_prompt(opts) end, {
      silent = false,
      noremap = true,
      desc = "[G]pt [P]rompt"
    })
    vim.keymap.set('n', '<leader>gpp', function () require('gpt').prompt(opts) end, {
      silent = true,
      noremap = true,
      desc = "[G]pt [P]rompt"
    })
    vim.keymap.set('n', '<leader>gpc', function () require('gpt').cancel(opts) end, {
      silent = true,
      noremap = true,
      desc = "[G]pt [C]ancel"
    })
    vim.keymap.set('i', '<C-g>p', function () require('gpt').prompt(opts) end, {
      silent = true,
      noremap = true,
      desc = "[G]pt [P]rompt"
    })
  -- vim.cmd [[highlight! default link CmpItemKind CmpItemMenuDefault]]
EOF

