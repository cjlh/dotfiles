# dotfiles

## Usage

### Dependencies

Instructions assume installation of [GNU Stow](https://www.gnu.org/software/stow/).

### Dry run

```
stow -nv */
```

### Link configs

```
# Neovim
brew install neovim ripgrep fd tree-sitter tree-sitter-cli basedpyright lua-language-server
stow neovim
```
