-- Disable legacy bridge language providers
-- See: https://github.com/neovim/neovim/blob/ac352a6d/runtime/doc/provider.txt
vim.g.loaded_python3_provider = 0
vim.g.loaded_ruby_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_node_provider = 0

require 'remaps'
require 'packages'
require 'options'
require 'colours'
