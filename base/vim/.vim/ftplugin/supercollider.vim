

if has("nvim") || version >= 801
nnoremap <buffer> <leader>sr :call SClang_block()<CR>
nnoremap <buffer> <M-R> :call SClang_block()<CR>
inoremap <buffer> <M-R> :call SClang_block()<CR>
vnoremap <buffer> <M-R> :call SClang_block()<CR>

nnoremap <buffer> <leader>r :call SClang_line()<CR>
nnoremap <buffer> <M-r> :call SClang_line()<CR>
inoremap <buffer> <M-r> :call SClang_line()<CR>
vnoremap <buffer> <M-r> :call SClang_line()<CR>
endif

