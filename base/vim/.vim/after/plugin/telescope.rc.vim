" vim:set ft=vim et sw=2:
if !exists('g:loaded_telescope')
  finish
endif

lua <<EOF
-- require('telescope').load_extension('fzy_native')
EOF

nnoremap <silent> <leader>ff <cmd>Telescope find_files hidden=true no_ignore=true<cr>
" nnoremap <silent> <leader>fl :Lines<cr>
nnoremap <silent> <leader>fb <cmd>Telescope buffers<cr>
nnoremap <silent> <leader>ft <cmd>Telescope tags<cr>
nnoremap <silent> <leader>bt :BTags<cr>
nnoremap <silent> <leader>fg <cmd>Telescope live_grep<cr>
nnoremap <silent> <leader>fgg <cmd>Telescope grep_string<cr>
nnoremap <silent> <leader>fn <cmd>Telescope file_browser hidden=true<cr>


"   " Insert mode completion
"   imap <c-x><c-k> <plug>(fzf-complete-word)
"   imap <c-x><c-f> <plug>(fzf-complete-path)
"   imap <c-x><c-l> <plug>(fzf-complete-line)

