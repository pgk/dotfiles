if !exists('g:loaded_lspsaga') | finish | endif

lua << EOF
local saga = require 'lspsaga'

saga.init_lsp_saga {
  error_sign = '●',
  warn_sign = '.',
  hint_sign = '♦',
  infor_sign = '.',
  border_style = "round",
  use_saga_diagnostic_sign = false,
  code_action_prompt = {
    enable = false,
    sign = false,
  },
}

EOF

" let g:ale_sign_error = '●'
" let g:ale_sign_warning = '.'
" let g:lsp_diagnostics_signs_error = {'text': '●'}
" let g:lsp_diagnostics_signs_warning = {'text': '.'} " icons require GUI
" let g:lsp_diagnostics_signs_hint = {'text': '♦'} " icons require GUI
nnoremap <silent><leader>gj :Lspsaga diagnostic_jump_next<CR>
nnoremap <silent><leader>gk <cmd>lua require('lspsaga.hover').render_hover_doc()<CR>
nnoremap <silent><leader>gh :Lspsaga lsp_finder<CR>
nnoremap <silent><leader>gp :Lspsaga preview_definition<CR>
nnoremap <silent><leader>gr :Lspsaga rename<CR>
" nnoremap <silent><leader>ga :Lspsaga code_action<CR>
