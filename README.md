# dotfiles

## Usage

### Dependencies

Instructions assume use of [GNU Stow](https://www.gnu.org/software/stow/)

```sh
brew install stow
```

### Dry run

```sh
stow -nv */
```

### Link configs

```sh
# Neovim (https://github.com/neovim/neovim)
brew install neovim ripgrep fd tree-sitter tree-sitter-cli basedpyright lua-language-server
stow neovim

# Kitty terminal (https://github.com/kovidgoyal/kitty)
stow kitty

# Fish shell (https://github.com/fish-shell/fish-shell)
stow fish

# Zed editor (https://github.com/zed-industries/zed)
stow zed

# OpenCode (https://github.com/anomalyco/opencode)
stow opencode
```
