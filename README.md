# dotfiles

## Usage

Instructions assume use of [GNU Stow](https://www.gnu.org/software/stow/):

```sh
brew install stow
```

To perform a dry run:

```sh
stow -nv */
```

To install apps and link configs:

```sh
# Neovim (https://github.com/neovim/neovim)
brew install neovim ripgrep fd tree-sitter tree-sitter-cli basedpyright lua-language-server
stow neovim

# Kitty terminal (https://github.com/kovidgoyal/kitty)
brew install --cask kitty
stow kitty

# Fish shell (https://github.com/fish-shell/fish-shell)
brew install fish
stow fish

# Zed editor (https://github.com/zed-industries/zed)
brew install --cask zed
stow zed

# OpenCode (https://github.com/anomalyco/opencode)
brew install anomalyco/tap/opencode
stow opencode
```
