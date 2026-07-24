-- Disable legacy bridge language providers
-- See: https://github.com/neovim/neovim/blob/ac352a6d/runtime/doc/provider.txt
vim.g.loaded_python3_provider = 0
vim.g.loaded_ruby_provider = 0
vim.g.loaded_perl_provider = 0
vim.g.loaded_node_provider = 0

-- Disable netrw
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

-- When opening directory from CLI arg, do not list contents
local function cd_into_directory_argument()
    if vim.fn.argc(-1) ~= 1 then
        return
    end

    local target = vim.fn.argv(0)

    if vim.fn.isdirectory(target) == 0 then
        return
    end

    local dir_buf = vim.fn.bufnr(vim.fn.fnamemodify(target, ':p'))

    vim.cmd.cd(target)
    vim.cmd.argdelete '*'

    if dir_buf ~= -1 then
        pcall(vim.api.nvim_buf_delete, dir_buf, { force = true })
    end
end

cd_into_directory_argument()

require 'remaps'
require 'packages'
require 'options'
require 'autocmd'
require 'commands'
require 'colours'
