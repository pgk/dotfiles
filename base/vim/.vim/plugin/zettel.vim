" This can be changed later.
let g:zettelkasten = "~/notes/"

function! g:ZettelProcessGrepLine(line)
	let parts = split(a:line, ':')
	if len(parts) < 1
		return ''
	endif

	let stripped_filename = substitute(parts[0], "\.md$", "", "")
	let new_link = '[['.split(stripped_filename, " ")[0] .']]'
	return new_link
endfunction


" function! g:ZettelNew(title)
" 	let full_title= strftime("%Y%m%d%H%M%S") . " " . a:title
" 	let fp = expand(g:zettelkasten) . substitute(full_title, " ", " ", "gi") . ".md"
" 	let md_title = '\# ' . full_title
" 	" execute '!touch' shellescape(fp)
" 	execute '!echo' shellescape(md_title) '>' shellescape(fp)
" 	execute ':e' fp
" endfunction
function! g:ZettelNew(title)
	" execute '!echo' shellescape(md_title) '>' shellescape(fp)
	" execute ':e' fp
	let cmd = 'nn new ' . shellescape(a:title)
	let out = system(cmd)
	" echo out
	execute ':e' out
endfunction

function! g:ZettelNewDaily()
	let cmd = 'nn daily'
	let out = system(cmd)
	execute ':e' out
endfunction

function! g:ZettelFollowNearestLink()
	let line=getline('.')
	let slugify_cmd='nn follow ' . shellescape(line)
	let slug=system(slugify_cmd)
	execute ':e ' slug
endfunction


command! -nargs=1 NewZettel call ZettelNew(<f-args>)
command! NewZettelDaily call ZettelNewDaily()
command! ZettelCopyTitle :let @" = expand("%") <CR>
command! FzfYankFile call fzf#run(fzf#wrap({'options': '--multi', 'sink': {line -> setreg('*', line)}}))
command! FzfYankFileGrep call fzf#run(fzf#wrap({'source': 'rg --column --line-number --no-heading --smart-case -- '.shellescape(<q-args>), 'options': '--multi', 'sink': {line -> setreg('*', ZettelProcessGrepLine(line))}}))
" command! ZettelFzfGoto call fzf#run(fzf#wrap({'source': 'rg --column --line-number --no-heading --smart-case -- '.shellescape(<q-args>), 'options': '--multi', 'sink': 'e'}))
command! ZettelFzfGoto call ZettelFollowNearestLink()

nnoremap <silent> <leader>zz :NewZettel 
nnoremap <silent> <leader>ZZ :NewZettelDaily<CR>
nnoremap <silent> <leader>fy :FzfYankFile<cr>
nnoremap <silent> <leader>fa :FzfYankFileGrep<cr>
nnoremap <silent> <leader>zl :ZettelFzfGoto<cr>
" Go to next wikilink [[
nnoremap <leader>zn /[[<CR>
nnoremap <leader>zp ?[[<CR>

" __REMAP_ZK LEADER-zif: find zettels in file
" nnoremap <leader>zif :lua require("configs.telescope").search_zettelkasten_in_files()<CR>
" __REMAP_ZK LEADER-zf: find zettels
" nnoremap <leader>zf :lua require("configs.telescope").search_zettelkasten()<CR>
" __REMAP_ZK LEADER-zl: find links
" nnoremap <leader>zl :lua require("configs.telescope").find_link()<CR>
" __REMAP_ZK LEADER-yf: Copy file name
" nnoremap <leader>yf :let @+=expand("%:t:r")<CR>      " Mnemonic: yank File Name
" __REMAP_ZK LEADER-§§: Open search for starting files
" nnoremap <leader>§§ :lua require("configs.telescope").open_starting_files()<CR>


