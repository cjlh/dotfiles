# Convenience aliases

# See https://allanmacgregor.com/posts/using-abbreviations-instead-of-aliases

abbr ll "ls -al"

abbr tt "tree -a -L 2"  # Get overview of current directory
abbr ttt "tree -a"      # Full tree

alias cdr "cd (git rev-parse --show-toplevel)"

abbr rgf "rg --hidden -F"

abbr vi "/usr/bin/vim"
abbr vim "nvim"

abbr ncat "nvimpager -c"

abbr gs "git status"
abbr ga "git add"
abbr gd "git diff"
abbr gd. "git diff ."
abbr gds "git diff --staged"
abbr gds. "git diff --staged ."
abbr gl "git log -n 10 --oneline"
abbr gcm "git commit -m"
abbr gca "git commit --amend"

abbr jj "just --unstable"
