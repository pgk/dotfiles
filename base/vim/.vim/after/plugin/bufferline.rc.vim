if !has('nvim') | finish | endif

lua << EOF
require("bufferline").setup{}
EOF

