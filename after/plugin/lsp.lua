-- https://github.com/neovim/nvim-lspconfig
-- https://docs.basedpyright.com/v1.21.0/installation/ides/
-- https://docs.astral.sh/ruff/editors/setup/#neovim

require('conform').setup {
    format_on_save = {
        timeout_ms = 500,
        lsp_format = 'fallback',
    },
    formatters_by_ft = {
        lua = { 'stylua' },
        python = { 'ruff_fix', 'ruff_format' },
    },
    default_format_opts = {
        lsp_format = 'fallback',
    },
}

vim.lsp.config('*', {
    root_markers = { '.git' },
})

vim.lsp.config('lua_ls', {
    settings = {
        Lua = {
            diagnostics = {
                globals = { 'vim', 'describe', 'it', 'before_each', 'after_each', 'Snacks' },
            },
        },
    },
})

vim.lsp.config('ruff', {
    -- init_options = {
    --     -- logLevel = 'debug',
    --     settings = {
    --         lint = { enable = false },
    --     },
    -- },
})

vim.lsp.config('basedpyright', {
    settings = {
        pyright = {
            -- Using Ruff's import organizer
            disableOrganizeImports = true,
        },
        python = {
            analysis = {
                -- Ignore all files for analysis to exclusively use Ruff for linting
                ignore = { '*' },
            },
        },
    },
})

vim.lsp.enable 'ruff'
vim.lsp.enable 'basedpyright'
vim.lsp.enable 'lua_ls'

vim.diagnostic.config {
    virtual_text = false,
    virtual_lines = {
        -- current_line = true
    },
}

vim.keymap.set('n', 'K', function()
    vim.lsp.buf.hover { border = 'rounded', max_height = 25, max_width = 120 }
end, { desc = 'Hover documentation (LSP)' })

vim.keymap.set('n', '<leader>F', function()
    require('conform').format()
end, { desc = 'Format and apply autofixes (Conform)' })

vim.api.nvim_set_keymap('n', 'gD', '<cmd>lua vim.lsp.buf.declaration()<CR>', { noremap = true, silent = true })
vim.api.nvim_set_keymap('n', 'gd', '<cmd>lua vim.lsp.buf.definition()<CR>', { noremap = true, silent = true })
