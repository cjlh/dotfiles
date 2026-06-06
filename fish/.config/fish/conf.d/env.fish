# Environment variables

set fish_greeting ""

fish_add_path "/usr/local/bin"

# Homebrew
fish_add_path "$HOME/.local/bin"
fish_add_path "/opt/homebrew/bin"

# subl utility
fish_add_path "/Applications/Sublime Text.app/Contents/SharedSupport/bin"

set -gx EDITOR nvim
set -gx HOMEBREW_NO_ANALYTICS 1
