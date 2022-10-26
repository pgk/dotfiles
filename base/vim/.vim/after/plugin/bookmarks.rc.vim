if !exists('g:bookmark_sign') | finish | endif

" let g:bookmark_save_per_working_dir = 1
" let g:bookmark_auto_save = 1

" let g:pgk_bookmarks_location = '~/.vim/pgk_bookmarks/'

" nmap <Leader>mm <Plug>BookmarkClear <bar> <plug>BookmarkToggle
" nmap <Leader>mi <Plug>BookmarkAnnotate
" nmap <Leader>ma <Plug>BookmarkShowAll
" " nmap <Leader>mj <Plug>BookmarkNext
" " nmap <Leader>mk <Plug>BookmarkPrev
" nmap <Leader>mc <Plug>BookmarkClear
" nmap <Leader>mx <Plug>BookmarkClearAll
" " nmap <Leader>mkk <Plug>BookmarkMoveUp
" " nmap <Leader>mjj <Plug>BookmarkMoveDown
" " nmap <Leader>mg <Plug>BookmarkMoveToLine

" if exists('g:loaded_fzf_vim')

" function! FzfAllBookmarkList()
"   let files = sort(bm#all_files())
"   call fzf#run({'source': files, 'sink': 'e', 'window': {'width': 0.9, 'height': 0.6}})
" endfunction

" nmap <Leader>ma :call FzfAllBookmarkList()<cr>

" endif
