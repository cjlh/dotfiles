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

vim.lsp.config('ruff', {
    init_options = {
        settings = {
            lint = { enable = false },
        },
    },
})

vim.lsp.enable('ruff')
vim.lsp.enable('basedpyright')
vim.lsp.enable('lua_ls')

vim.diagnostic.config({
    virtual_text = false,
    virtual_lines = {
        -- current_line = true
    },
})

vim.keymap.set('n', 'K', function()
  vim.lsp.buf.hover { border = "rounded", max_height = 25, max_width = 120 }
end, { desc = "Hover documentation" })

