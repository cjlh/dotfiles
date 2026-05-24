-- https://github.com/neovim/nvim-lspconfig
-- https://docs.basedpyright.com/v1.21.0/installation/ides/

vim.lsp.config('*', {
    root_markers = { ".git" },
})

vim.lsp.config('lua_ls', {
    settings = {
        Lua = {
            diagnostics = {
                globals = { "vim", "describe", "it", "before_each", "after_each" },
            },
        },
    },
})

vim.lsp.enable('basedpyright')
vim.lsp.enable('lua_ls')

vim.diagnostic.config({
    virtual_text = false,
    virtual_lines = {
        -- current_line = true
    },
})

