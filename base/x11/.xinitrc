xmodmap "clear lock"
xmodmap "keycode 66 = Escape NoSymbol Escape"
xmodmap "keycode 9 = Escape NoSymbol Escape"

xmodmap ~/dotfiles/base/x11/xmodmap-esc
xset r rate 150 50

xbindkeys

xautolock -time 15 -locker slock &

dwmstatus 2>&1 >/dev/null &

feh --bg-fill --randomize ~/dotfiles/wallpapers/* %

exec dwm
