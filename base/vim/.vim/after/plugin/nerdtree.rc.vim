if !exists('g:loaded_nerd_tree')
  finish
endif

" NERDTree settings
let g:NERDTreeShowHidden = 1
let g:NERDTreeAutoDeleteBuffer=1
let NERDTreeShowHidden=1
let g:NERDTreeCreatePrefix='silent keepalt keepjumps'

nnoremap  <Leader>nf :NERDTreeFind<CR>

call NERDTreeAddKeyMap({
        \ 'key': 'yy',
        \ 'callback': 'NERDTreeYankCurrentNode',
        \ 'quickhelpText': 'put full path of current node into the default register' })

function! NERDTreeYankCurrentNode()
    let n = g:NERDTreeFileNode.GetSelected()
    if n != {}
        call setreg('"', n.path.str())
        call setreg('+', n.path.str())
    endif
endfunction
