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
# Neovim
brew install neovim ripgrep fd tree-sitter tree-sitter-cli basedpyright lua-language-server
stow neovim

# Kitty terminal
stow kitty
```
