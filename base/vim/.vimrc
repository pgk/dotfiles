" -------------------
" VIMRC
"--------------------

set nocompatible
set encoding=utf-8
set hidden


" Having longer updatetime (default is 4000 ms = 4 s) leads to noticeable
" delays and poor user experience.
set updatetime=50

" Don't pass messages to |ins-completion-menu|.
set shortmess+=c

set number
set relativenumber
set mouse=a
set splitbelow
set splitright

set ignorecase
set smartcase

" Set the terminal to be zsh
set shell=/bin/bash

set history=200        " keep more lines of command line history
set ruler              " show the cursor position all the time
set showcmd            " display incomplete commands
set incsearch          " do incremental searching
set scrolloff=5        " Maintain more context around the cursor
set visualbell         " No sound plz.
set autoread           " Reread a file when it's changed outside of vim.

" Install vim-plug if missing
if empty(glob('~/.vim/autoload/plug.vim'))
  silent !curl -fLo ~/.vim/autoload/plug.vim --create-dirs
    \ https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
  autocmd VimEnter * PlugInstall --sync | source $MYVIMRC
endif

call plug#begin('~/.vim/plugged')

Plug 'tpope/vim-sensible'
Plug 'tpope/vim-fugitive'
Plug 'tpope/vim-surround'
Plug 'tpope/vim-repeat'
Plug 'tpope/vim-commentary'

Plug 'editorconfig/editorconfig-vim'
Plug 'scrooloose/nerdtree'
Plug 'leafgarland/typescript-vim'
Plug 'glench/vim-jinja2-syntax'
Plug 'cespare/vim-toml'
Plug 'tomasr/molokai'

Plug 'ludovicchabant/vim-gutentags'

if has('nvim') || version >= 801
  Plug 'supercollider/scvim'
  Plug 'neomake/neomake'
  if executable('go')
    Plug 'fatih/vim-go', { 'do': ':GoUpdateBinaries' }
  endif
  Plug 'w0rp/ale'
endif


if version >= 704
  Plug 'junegunn/fzf', { 'dir': '~/.fzf', 'do': './install --bin' }
  Plug 'junegunn/fzf.vim'
endif

if has('nvim')
  Plug 'kassio/neoterm'
endif

if has('python3')
  Plug 'vim-vdebug/vdebug'
endif

call plug#end()

" --------- end plugins ----------

" Set ag for ack.vim and fzf
if executable('ag')
  let g:ackprg = 'ag --vimgrep'
  let $FZF_DEFAULT_COMMAND = 'ag --hidden --ignore .git -g ""'
else
  let $FZF_DEFAULT_COMMAND = "find . -type f -not -path '*/\.git/*'"
endif

" NERDTree settings
let g:NERDTreeShowHidden = 1
let g:NERDTreeAutoDeleteBuffer=1
let NERDTreeShowHidden=1
let g:NERDTreeCreatePrefix='silent keepalt keepjumps'

" NetRW settings.
let g:netrw_browse_split = 2
let g:netrw_banner = 0
let g:netrw_winsize = 25
let g:netrw_liststyle = 3
let g:netrw_browse_split = 4
let g:netrw_altv = 1

" Gutentag setup
let g:gutentags_cache_dir = '~/.vim/gutentags'
let gutentags_ctags_exclude = ['*.css', '*.html', '*.js', '*.json', '*.xml',
                              \ '*.phar', '*.ini', '*.rst', '*.md',
                              \ '*vendor/*/test*', '*vendor/*/Test*',
                              \ '*vendor/*/fixture*', '*vendor/*/Fixture*',
                              \ '*var/cache*', '*var/log*']

" Status line setup
function! GitBranch()
    return system("command -v git > /dev/null 2>&1 && git rev-parse --abbrev-ref HEAD 2>/dev/null | tr -d '\n'")
endfunction

function! StatuslineGit()
    let l:branchname = GitBranch()
    return strlen(l:branchname) > 0?'  '.l:branchname.' ':''
endfunction

set statusline=
set statusline+=%#PmenuSel#
set statusline+=%{StatuslineGit()}
set statusline+=%#LineNr#
set statusline+=\ %f
set statusline+=\ %m
set statusline+=%=
set statusline+=%#CursorColumn#
set statusline+=\ %y
set statusline+=\ %{&fileencoding?&fileencoding:&encoding}
set statusline+=\[%{&fileformat}\]
set statusline+=\ %p%%
set statusline+=\ %l:%c
set statusline+=\ 
" End Statusline

if has("nvim") && $COLORTERM =~? 'truecolor'
  set termguicolors
endif

set background=dark
colorscheme molokai

function! SetLightColour()
  set background=light
  execute 'colorscheme morning'
endfunction

function! SetDarkColour()
  set background=dark
  execute 'colorscheme molokai'
endfunction

if has("nvim") || has("terminal")
  let g:scTerminalBuffer = "on"
endif

function! PInsert2(item)
  let @z=a:item
  norm "zp
  call feedkeys('a')
endfunction

function! CompleteInf()
  let nl=[]
  let l=complete_info()
  for k in l['items']
    call add(nl, k['word']. ' : ' .k['info'] . ' '. k['menu'] )
  endfor
  call fzf#vim#complete(fzf#wrap({ 'source': nl,'reducer': { lines -> split(lines[0], '\zs :')[0] },'sink':function('PInsert2')}))
endfunction 

imap <c-'> <CMD>:call CompleteInf()<CR>

set path+=** " Provides tab-completion for all file-related tasks

" Set completion
if has('nvim') || version >= 801
  " Ale setup
  let g:ale_completion_enabled = 1
  " Fine-tune when linters run.
  let g:ale_lint_on_text_changed = 'never'
  let g:ale_lint_on_insert_leave = 1
  " don't want linters to run on opening a file
  let g:ale_lint_on_enter = 0
  set omnifunc=ale#completion#OmniFunc

  let g:ale_linters = {
  \   'php': ['php'],
  \}
else
  set omnifunc=syntaxcomplete#Complete
endif


" allow backspacing over everything in insert mode
set backspace=indent,eol,start

" Always show the signcolumn, otherwise it would shift the text each time
" diagnostics appear/become resolved.
if has("patch-8.1.1564")
  " Recently vim can merge signcolumn and number column into one
  set signcolumn=number
elseif version >= 800
  set signcolumn=yes
endif

if has("vms")
  set nobackup         " do not keep a backup file, use versions instead
else
  set backup           " keep a backup file
endif

" Temporary backups go to central place.
set backupdir=~/.vim-tmp,~/.tmp,~/tmp,/var/tmp,/tmp
set directory=~/.vim-tmp,~/.tmp,~/tmp,/var/tmp,/tmp

" Enable extended % matching
runtime macros/matchit.vim

if has("wildmenu")
  set wildmenu
  set wildmode=list:longest
  " Ignore those files by default.
  set wildignore+=*/tmp/*,*/node_modules/*,*.so,*.swp,*.zip    " MacOSX/Linux
  set wildignore+=*\\tmp\\*,*.swp,*.zip,*.exe                  " Windows
  set wildignore+=*.a,*.o
  set wildignore+=*.bmp,*.gif,*.ico,*.jpg,*.png
  set wildignore+=.DS_Store,.git,.hg,.svn
  if exists("&wildignorecase")
      set wildignorecase
  endif
endif

" text appearance
set nowrap                                " nowrap by default
set list                                  " show invisible characters
set listchars=tab:»·,trail:·,nbsp:·,eol:¬ " Display extra whitespace

" persistent undo between file reloads
if has('persistent_undo')
  " Set the undofile dir to be something else than .
  set undofile
  set undodir=~/.vim/tmp
endif

" KEYBOARD MAPPINGS ----------------------------------------------------- {{{

" Map leader first
let g:mapleader = " "

" Space should really do nothing.
nnoremap <Space> <Nop>

" NERDTree
nnoremap <Leader>nt :NERDTreeToggle<CR>

" Copy to and paste from system clipboard
vnoremap <silent> <leader>y "+y
nnoremap <silent> <leader>Y "+yg_
nnoremap <silent> <leader>y "+y
nnoremap <silent> <leader>p "+p
nnoremap <silent> <leader>P "+P
vnoremap <silent> <leader>p "+p
vnoremap <silent> <leader>P "+P

" Leader-based window movement
nnoremap <silent> <leader>j <C-w>j
nnoremap <silent> <leader>k <C-w>k
nnoremap <silent> <leader>h <C-w>h
nnoremap <silent> <leader>l <C-w>l
nnoremap <silent> <leader>ws :split<cr>
nnoremap <silent> <leader>wv :vsplit<cr>
nnoremap <silent> <leader>wc <C-w>c
nnoremap <silent> <leader>WW <C-w>o
nnoremap <silent> <leader>ww <C-w>w
nnoremap <silent> <leader>w= :exe "resize " . (winheight(0) * 3/2)<CR>
nnoremap <silent> <leader>w- :exe "resize " . (winheight(0) * 2/3)<CR>

" Buffer mappings
nnoremap <silent> [b :bprevious<CR>
nnoremap <silent> ]b :bnext<CR>
noremap <silent> [B :bfirst<CR>
nnoremap <silent> ]B :blast<CR>

" hide matches on <leader>space
nnoremap <silent> <leader><space> :nohlsearch<cr>

" Don't use Ex mode, use Q for executing current line and reading back the result. Revert with ":unmap Q".
nnoremap Q !!sh<CR>

" CTRL-U in insert mode deletes a lot.  Use CTRL-G u to first break undo,
" so that you can undo CTRL-U after inserting a line break.
inoremap <C-U> <C-G>u<C-U>

" Remap Greek letters to normal mode letters
" Not all chars can be cleanly remapped though, for example q and ;
nnoremap ς w
nnoremap τ t
nnoremap υ y
nnoremap υυ yy
nnoremap Υ Υ
nnoremap Θ U
nnoremap θ u
nnoremap ο ο
nnoremap ι i
nnoremap Ι I
nnoremap Ο O
nnoremap π p
nnoremap Π P

nnoremap α a
nnoremap Α A
nnoremap σ s
nnoremap δ d
nnoremap δδ dd
nnoremap φ f
nnoremap γ g
nnoremap η h
nnoremap ξ j
nnoremap κ k
nnoremap λ l

nnoremap ζ z
nnoremap χ x
nnoremap ψ c
nnoremap ω v
nnoremap Ω V
nnoremap β b
nnoremap Β B
nnoremap ν n
nnoremap Ν N
nnoremap μ m

" Do not recognize octal numbers for Ctrl-A and Ctrl-X, most users find it confusing.
set nrformats-=octal

command! Ctgen !ctags -R --exclude=.git --exclude=node_modules --exclude=vendor --exclude=logs .

command! Rlvimrc :source ~/.vimrc
command! Evimrc :e ~/.vimrc

function! EditStandups()
  :e ~/Sync/docs/standups.md
  :normal gg
endfunction

command! Standup call EditStandups()
command! Clight call SetLightColour()
command! Cdark call SetDarkColour()

if executable('rg')
  nnoremap <Leader>a :Rg<cr>
  nnoremap <silent><leader>aa :Rg <C-R><C-W><CR>
elseif executable('ag')
  nnoremap <Leader>a :Ag<cr>
  nnoremap <silent><leader>aa :Ag <C-R><C-W><CR>
else
  nnoremap <Leader>a :grep<cr>
  nnoremap <silent><Leader>aa :grep <cword> *<CR>
endif

nnoremap <silent> <leader>ff :FZF<cr>
nnoremap <silent> <leader>fl :Lines<cr>
nnoremap <silent> <leader>fb :Buffers<cr>
nnoremap <silent> <leader>ft :Tags<cr>


if has('nvim')
  " Insert mode completion
  imap <c-x><c-k> <plug>(fzf-complete-word)
  imap <c-x><c-f> <plug>(fzf-complete-path)
  imap <c-x><c-l> <plug>(fzf-complete-line)
endif

if has('nvim') || has('terminal')
  " Easily go to normal mode from terminal
  " tnoremap <Esc> <C-\><C-n>
  " map the actual escape.
  " tnoremap <M-[> <Esc>

  " Terminal mode:
  tnoremap <M-h> <c-\><c-n><c-w>h
  tnoremap <M-j> <c-\><c-n><c-w>j
  tnoremap <M-k> <c-\><c-n><c-w>k
  tnoremap <M-l> <c-\><c-n><c-w>l
  " Insert mode:
  inoremap <M-h> <Esc><c-w>h
  inoremap <M-j> <Esc><c-w>j
  inoremap <M-k> <Esc><c-w>k
  inoremap <M-l> <Esc><c-w>l
  " Visual mode:
  vnoremap <M-h> <Esc><c-w>h
  vnoremap <M-j> <Esc><c-w>j
  vnoremap <M-k> <Esc><c-w>k
  vnoremap <M-l> <Esc><c-w>l
  " Normal mode:
  nnoremap <M-h> <c-w>h
  nnoremap <M-j> <c-w>j
  nnoremap <M-k> <c-w>k
  nnoremap <M-l> <c-w>l
endif

" Switch syntax highlighting on, when the terminal has colors
" Also switch on highlighting the last used search pattern.
if &t_Co > 2 || has("gui_running")
  syntax on
  set hlsearch
endif

" Only do this part when compiled with support for autocommands.
if has("autocmd")
  " Enable file type detection.
  filetype plugin indent on
  au Filetype go nnoremap <leader>r :GoRun %<CR>
  " Put these in an autocmd group, so that we can delete them easily.
  augroup vimrcEx
  au!

  autocmd FileType javascript setlocal ts=4 sts=4 sw=4
  autocmd BufNewFile,BufRead *.tsx set syntax=ts

  " When editing a file, always jump to the last known cursor position.
  " Don't do it when the position is invalid or when inside an event handler
  " (happens when dropping a file on gvim).
  " Also don't do it when the mark is in the first line, that is the default
  " position when opening a file.
  autocmd BufReadPost *
    \ if line("'\"") > 1 && line("'\"") <= line("$") |
    \   exe "normal! g`\"" |
    \ endif

  " key bindings
  if has("nvim") || version >= 801
    au Filetype supercollider nnoremap <buffer> <leader>sr :call SClang_block()<CR>
    au Filetype supercollider nnoremap <buffer> <M-R> :call SClang_block()<CR>
    au Filetype supercollider inoremap <buffer> <M-R> :call SClang_block()<CR>
    au Filetype supercollider vnoremap <buffer> <M-R> :call SClang_block()<CR>

    au Filetype supercollider nnoremap <buffer> <leader>r :call SClang_line()<CR>
    au Filetype supercollider nnoremap <buffer> <M-r> :call SClang_line()<CR>
    au Filetype supercollider inoremap <buffer> <M-r> :call SClang_line()<CR>
    au Filetype supercollider vnoremap <buffer> <M-r> :call SClang_line()<CR>
  endif
  augroup END
else
  set autoindent " always set autoindenting on
endif " has("autocmd")

" Pretty fonts.
if has("gui_running")
    if has("gui_gtk2")
      :set guifont=Inconsolata:h18,Luxi\ Mono\ 12:h14
    elseif has("x11")
" Also for GTK 1
      :set guifont=Liberation\ Mono\ 12
    elseif has("gui_win32")
      :set guifont=Luxi_Mono:h14:cANSI
    elseif has("gui_macvim")
      :set guifont=Inconsolata:h18,Menlo:h16,Consolas:h16,DejaVu\ Sans\ Mono:h16,monospace:h16
    endif
endif

" Convenient command to see the difference between the current buffer and the
" file it was loaded from, thus the changes you made.
" Only define it when not defined already.
" Revert with: ":delcommand DiffOrig".
if !exists(":DiffOrig")
  command DiffOrig vert new | set bt=nofile | r ++edit # | 0d_ | diffthis
                          \ | wincmd p | diffthis
endif

" When vim is started at a folder containing a .lvimrc.vim, source it. Fail
" silently if not.
silent! so .lvimrc.vim
" END Vimrc.
