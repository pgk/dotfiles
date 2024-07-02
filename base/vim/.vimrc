" -------------------
" VIMRC
"--------------------
"
" vim:set ft=vim et sw=2:

set nocompatible
set encoding=utf-8
set hidden

set number
set relativenumber
set mouse=a
set splitbelow
set splitright

set ignorecase
set smartcase

" Set the terminal shell.
set shell=/bin/bash

set shortmess+=c       " Don't pass messages to |ins-completion-menu|.
set updatetime=50      " Set a much lower updatetime.
set history=10000      " keep more lines of command line history
set ruler              " show the cursor position all the time
set showcmd            " display incomplete commands
set incsearch          " do incremental searching
set scrolloff=5        " Maintain more context around the cursor
set visualbell         " No sound plz
set autoread           " Reread a file when it's changed outside of vim.
set exrc               " Check if there are dir-specific config files.
set tabpagemax=50
set laststatus=2
set sidescrolloff=5
set display+=lastline
set sessionoptions-=options
set viewoptions-=options
set backspace=indent,eol,start            " allow backspacing over everything in insert mode
set lazyredraw

" text appearance
set nowrap                                " nowrap by default
set list                                  " show invisible characters
set listchars=tab:»·,trail:·,nbsp:·,eol:¬ " Display extra whitespace

set complete-=i
set nrformats-=octal  " Do not recognize octal numbers for Ctrl-A and Ctrl-X, most users find it confusing.

if has('clipboard') && has('nvim')
  set clipboard=unnamedplus
endif

if has('autocmd')
  filetype plugin indent on
endif
if has('syntax') && !exists('g:syntax_on')
  syntax enable
endif

if !has('nvim') && &ttimeoutlen == -1
  set ttimeout
  set ttimeoutlen=100
endif

if v:version > 703 || v:version == 703 && has("patch541")
  set formatoptions+=j " Delete comment character when joining commented lines
endif

if empty(mapcheck('<C-U>', 'i'))
  inoremap <C-U> <C-G>u<C-U>
endif
if empty(mapcheck('<C-W>', 'i'))
  inoremap <C-W> <C-G>u<C-W>
endif

call plug#begin('~/.vim/plugged')

" Tpope stuff.
" Plug 'tpope/vim-sensible'
" Plug 'tpope/vim-fugitive'
Plug 'tpope/vim-surround'
Plug 'tpope/vim-repeat'
Plug 'tpope/vim-commentary'

Plug 'editorconfig/editorconfig-vim'
Plug 'scrooloose/nerdtree'
Plug 'leafgarland/typescript-vim'
Plug 'stanangeloff/php.vim'
" Plug 'glench/vim-jinja2-syntax'
Plug 'leafOfTree/vim-svelte-plugin'
Plug 'mattn/emmet-vim'

Plug 'tomasr/molokai'
Plug 'altercation/vim-colors-solarized'

Plug 'junegunn/goyo.vim'
Plug 'junegunn/limelight.vim'
Plug 'junegunn/seoul256.vim'

" Plug 'mhinz/vim-startify'
if has('nvim')
  " Plug 'nvim-lualine/lualine.nvim'
  " Plug 'akinsho/bufferline.nvim'
  " Fancy icons.
  " Plug 'kyazdani42/nvim-web-devicons'
else
  " Plug 'vim-airline/vim-airline'
  " Plug 'vim-airline/vim-airline-themes'
endif

Plug 'gioele/vim-autoswap'
" Plug 'vim-scripts/dbext.vim'
Plug 'jiangmiao/auto-pairs'

" ctags
if executable('ctags') && empty($VIM_SIMPLE)
  " Plug 'ludovicchabant/vim-gutentags'
endif

if has('python3') && empty($VIM_SIMPLE)
  " Plug 'vim-vdebug/vdebug'
  Plug 'SirVer/ultisnips'
  Plug 'honza/vim-snippets'
  Plug 'vim-vdebug/vdebug'
endif

if has('nvim')
  Plug 'folke/tokyonight.nvim', { 'branch': 'main' }
endif

if has('nvim') && has('nvim-0.6') && empty($VIM_SIMPLE)
  " Plug 'rcarriga/nvim-notify'
  Plug 'neovim/nvim-lspconfig'
  Plug 'onsails/lspkind-nvim'
  Plug 'hrsh7th/cmp-nvim-lsp'
  Plug 'hrsh7th/cmp-buffer'
  Plug 'hrsh7th/cmp-path'
  Plug 'hrsh7th/cmp-cmdline'
  Plug 'hrsh7th/nvim-cmp'
  " Plug 'glepnir/lspsaga.nvim'
  Plug 'github/copilot.vim'

  if has('python3')
    Plug 'quangnguyen30192/cmp-nvim-ultisnips'
  endif

  if has('macunix')
    Plug 'rizzatti/dash.vim'
  endif

  Plug 'norcalli/nvim-colorizer.lua'
  Plug 'nvim-treesitter/nvim-treesitter', {'do': ':TSUpdate'}  " We recommend updating the parsers on update
  Plug 'nvim-treesitter/nvim-treesitter-textobjects'

  " Plug 'nvim-lua/plenary.nvim'
  " Plug 'nvim-telescope/telescope.nvim'
  " Plug 'nvim-telescope/telescope-fzy-native.nvim'

  " Debugging Plugins
  Plug 'mfussenegger/nvim-dap'
  Plug 'Pocco81/DAPInstall.nvim'
endif

if version >= 704
  Plug 'junegunn/fzf', { 'dir': '~/.fzf', 'do': './install --bin' }
  Plug 'junegunn/fzf.vim'
endif

call plug#end()

" --------- end plugins ----------
set completeopt=menu,menuone,noselect

if has("nvim") && $COLORTERM =~? 'truecolor'
  set termguicolors
endif

let g:solarized_termcolors=256
" set background=dark
" set background=light
" if has('nvim')
"   " colorscheme solarized
"   " colorscheme tokyonight
"   " colorscheme peachpuff
" else
"   " colorscheme solarized
"   " colorscheme peachpuff
" endif
colorscheme molokai

function! SetLightColour()
  set background=light
  execute 'set background=light'
  execute 'colo seoul256'
endfunction

function! SetDarkColour()
  set background=dark
  execute 'set background=dark'
  " execute 'colorscheme molokai'
  execute 'colorscheme tokyonight'
endfunction

set path+=** " Provides tab-completion for all file-related tasks

" Set completion defaults
if !has('nvim') && version < 801
  set omnifunc=syntaxcomplete#Complete
endif

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

" Map Y to yank till end of line.
nnoremap Y y$
" map n to center the cursor.
nnoremap n nzzzv
" map N to center the cursor.
nnoremap N Nzzzv

nnoremap <Leader>nt :NERDTreeToggle<CR>
nnoremap <Leader>q :q<CR>

let g:UltiSnipsSnippetDirectories=["UltiSnips"]
let g:UltiSnipsExpandTrigger="<tab>"
" Copy to and paste from system clipboard
vnoremap <silent> <leader>y "+y
nnoremap <silent> <leader>Y "+yg_
nnoremap <silent> <leader>y "+y
nnoremap <silent> <leader>p "+p
nnoremap <silent> <leader>P "+P
vnoremap <silent> <leader>p "+p
vnoremap <silent> <leader>P "+P


" Leader-based window movement
nnoremap <silent> <leader>wj <C-w>j
nnoremap <silent> <leader>wk <C-w>k
nnoremap <silent> <leader>wh <C-w>h
nnoremap <silent> <leader>wl <C-w>l
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
nmap ς w
nmap τ t
nmap υ y
nmap υυ yy
nmap Υ Υ
nmap Θ U
nmap θ u
nmap ο ο
nmap ι i
nmap Ι I
nmap Ο O
nmap π p
nmap Π P
nmap ΅ W

nmap α a
nmap Α A
nmap σ s
nmap δ d
nmap φ f
nmap γ g
nmap γγ gg
nmap Γ G
nmap δδ dd
nmap φ f
nmap Φ F
nmap γ g
nmap ς w
nmap ¨ :
nmap ΄ ;

nmap η h
nmap ξ j
nmap κ k
nmap λ l
vmap η h
vmap ξ j
vmap κ k
vmap λ l

nmap ζ z
nmap χ x
nmap ψ c
nmap ω v
nmap Ω V
nmap β b
nmap Β B
nmap ν n
nmap Ν N
nmap μ m

command! Ctgen !ctags -R --exclude=.git --exclude=node_modules --exclude=vendor --exclude=logs .

command! Rlvimrc :source ~/.vimrc
command! Evimrc :e ~/.vimrc
command! Ecommonplace :e ~/Sync/docs/wikis/commonplace.txt
command! Rcommonplace :!python3 ~/Sync/docs/wikis/render_commonplace.py ~/Sync/docs/wikis/commonplace.txt

command! Clight call SetLightColour()
command! Cdark call SetDarkColour()
command! -nargs=0 Scb call Newscratch()

if !exists('g:loaded_telescope') && !exists('g:loaded_fzf_vim')
  nnoremap <Leader>a :grep<cr>
  nnoremap <silent><Leader>aa :grep <cword> *<CR>
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
  " Put these in an autocmd group, so that we can delete them easily.
  augroup vimrcEx
  au!

  autocmd FileType javascript setlocal ts=4 sts=4 sw=4

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
  augroup END
else
  set autoindent " always set autoindenting on
endif " has("autocmd")

" Pretty fonts in GUIS.
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

" Function to source only if file exists {
function! SourceIfExists(file)
  if filereadable(expand(a:file))
    exe 'source' a:file
  endif
endfunction
" }.

call SourceIfExists("~/.vim-default-colors.vim")

" END Vimrc
