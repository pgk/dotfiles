if !exists('g:loaded_colorizer')
  finish
endif

if !has("nvim") || !($COLORTERM =~? 'truecolor')
  finish
endif

lua << EOF
require'colorizer'.setup{
  '*';                             -- Highlight all files by default.
  '!vim';                          -- Exclude vim from highlighting.
}
-- #FAFAFA
EOF
