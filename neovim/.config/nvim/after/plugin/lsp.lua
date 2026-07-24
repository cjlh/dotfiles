-- https://github.com/neovim/nvim-lspconfig
-- https://docs.basedpyright.com/v1.21.0/installation/ides/
-- https://docs.astral.sh/ruff/editors/setup/#neovim

--[[
    See `:help lsp-defaults` for all defaults. Default keymaps:
      - "gra" (Normal and Visual mode) is mapped to |vim.lsp.buf.code_action()|
      - "gri" is mapped to |vim.lsp.buf.implementation()|
      - "grn" is mapped to |vim.lsp.buf.rename()|
      - "grr" is mapped to |vim.lsp.buf.references()|
      - "grt" is mapped to |vim.lsp.buf.type_definition()|
      - "grx" is mapped to |vim.lsp.codelens.run()|
      - "gO" is mapped to |vim.lsp.buf.document_symbol()|
      - CTRL-S (Insert mode) is mapped to |vim.lsp.buf.signature_help()|
      - |v_an| and |v_in| fall back to LSP |vim.lsp.buf.selection_range()| if
        treesitter is not active.
      - |gx| handles `textDocument/documentLink`. Example: with gopls, invoking gx
        on "os" in this Go code will open documentation externally: >
          package nvim
          import (
             "os"
          )
]]

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
    virtual_text = true,
    virtual_lines = false,
}

vim.lsp.completion.enable()
vim.lsp.inlay_hint.enable(true)

vim.keymap.set('n', 'K', function()
    vim.lsp.buf.hover { border = 'rounded', max_height = 25, max_width = 120 }
end, { desc = 'Hover documentation (LSP)' })

vim.keymap.set('n', '<leader>F', function()
    require('conform').format()
end, { desc = 'Format and apply autofixes (Conform)' })
