if !exists('g:loaded_gutentags')
  finish
endif

" Gutentags setup
let g:gutentags_project_root = ['wp-content', '.phab', '.git', '.hg', '.svn', '.fslckout', '_FOSSIL_']
let g:gutentags_cache_dir = '~/.vim/gutentags'
let g:gutentags_ctags_exclude = ['*.xml',
                              \ '*.phar', '*dist/*',
                              \ '*vendor/*/test*', '*vendor/*/Test*',
                              \ "base/phpdev/wpcs", "base/phpdev/vendor", "base/phpdev/phpactor",
                              \ '*vendor/*/fixture*', '*vendor/*/Fixture*',
                              \ '*.min.js', '*.min.css',
                              \ '.git', '.hg', '.svn',
                              \ '*var/cache*', '*var/log*']

