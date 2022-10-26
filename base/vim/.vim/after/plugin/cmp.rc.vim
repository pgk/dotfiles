if !exists('g:loaded_cmp') | finish | endif

set completeopt=menuone,noinsert,noselect

lua <<EOF
  local cmp = require'cmp'
  local lspkind = require('lspkind')
  lspkind.init()

  cmp.setup({
    formatting = {
      format = lspkind.cmp_format({
      with_text = true, -- show text alongside icons
      maxwidth = 50, -- prevent the popup from showing more than provided characters (e.g 50 will not show more than 50 characters)
      menu = {
        buffer = "[buf]",
        nvim_lsp = "[LSP]",
        path = "[path]",
        ultisnips = "[snip]",
      },

      -- The function below will be called before any actual modifications from lspkind
      -- so that you can provide more controls on popup customization. (See [#30](https://github.com/onsails/lspkind-nvim/pull/30))
    })
    },
    snippet = {
      expand = function(args)
        vim.fn["UltiSnips#Anon"](args.body)
      end,
    },
    mapping = {
      ['<C-b>'] = cmp.mapping(cmp.mapping.scroll_docs(-4), { 'i', 'c' }),
      ['<C-f>'] = cmp.mapping(cmp.mapping.scroll_docs(4), { 'i', 'c' }),
      ['<C-Space>'] = cmp.mapping(cmp.mapping.complete(), { 'i', 'c' }),
      ['<C-y>'] = cmp.config.disable, -- Specify `cmp.config.disable` if you want to remove the default `<C-y>` mapping.
      ['<C-e>'] = cmp.mapping({
        i = cmp.mapping.abort(),
        c = cmp.mapping.close(),
      }),
      ['<CR>'] = cmp.mapping.confirm({ select = true }), -- Accept currently selected item. Set `select` to `false` to only confirm explicitly selected items.
    },
    sources = cmp.config.sources({
      { name = 'nvim_lsp' },
      { name = "path" },
      { name = 'ultisnips' },
      { name = "buffer", keyword_length = 5 },
    }, {
      { name = 'buffer' },
    }),
    experimental = {
      -- I like the new menu better! Nice work hrsh7th
      native_menu = false,

      -- Let's play with this for a day or two
      ghost_text = false,
    },
  })

  -- vim.cmd [[highlight! default link CmpItemKind CmpItemMenuDefault]]
EOF

  " nnoremap <Leader>gd :ALEGoToDefinition<CR>
  " nnoremap <Leader>gy :ALEGoToTypeDefinition<CR>
  " nnoremap <Leader>gr :ALEFindReferences<CR>
  " nnoremap <Leader>an :ALENextWrap<CR>
  " nnoremap <Leader>al :ALELint<CR>
  " nnoremap <Leader>af :ALEFix<CR>
