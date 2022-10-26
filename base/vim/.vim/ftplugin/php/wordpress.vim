" wordpress-specific PHP stuff.

" set keywordprg=phpman
"
"
" set keywordprg=phpman
"
" nnoremap <leader>k :terminal phpman <cword><cr>
" nnoremap <silent><Leader>K :Tnew<CR> :T phpman expand(<cword>)


" Basics
set noexpandtab
set tabstop=4
set shiftwidth=4


let g:ale_php_phpcs_executable = 'phpcs-wp'
let g:ale_php_phpcbf_standard = 'WordPress'

let g:ale_php_phpcbf_executable = 'phpcbf-wp'
let g:ale_php_phpcbf_standard = 'WordPress'

let g:ale_php_psalm_executable = 'psalm-wp'


let g:ale_fixers = {'php': ['phpcbf']}
let g:ale_linters = {
\   'php': ['php', 'phpcs'],
\}


