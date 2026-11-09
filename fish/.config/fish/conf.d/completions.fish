# Add unstaged changes to neovim and git completion
complete -c nvim -k -a '(git ls-files --modified --others --exclude-standard 2>/dev/null)' -d 'git changed'
complete -c git -k -a '(git ls-files --modified --others --exclude-standard 2>/dev/null)' -d 'git changed'
