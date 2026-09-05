#!/bin/zsh
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"
DIR="${0:A:h}"
python3 "$DIR/gen_dashboard.py"
open "$DIR/dashboard.html"
