if !exists('g:loaded_copilot') | finish | endif

let g:copilot_filetypes = {
      \ '*': v:false,
      \ 'php': v:true,
      \ 'go': v:true,
      \ 'python': v:true,
      \ 'javascript': v:true,
      \ 'typescript': v:true,
      \ 'html': v:true,
      \ 'css': v:true,
      \ }
" imap <silent><script><expr> <C-> copilot#Accept("\<CR>")
        " let g:copilot_no_tab_map = v:true
nnoremap <silent> <leader>CC :Copilot enable<cr>
nnoremap <silent> <leader>CD :Copilot disable<cr>
nnoremap <silent> <leader>CS :Copilot status<cr>
