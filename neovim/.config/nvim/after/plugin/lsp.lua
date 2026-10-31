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

-- Returns a Conform format callback which reports how many of the original lines were changed
local function report_format_changes(bufnr)
    bufnr = bufnr == 0 and vim.api.nvim_get_current_buf() or bufnr

    local before = table.concat(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false), '\n') .. '\n'
    local total = vim.api.nvim_buf_line_count(bufnr)

    return function(err, did_edit)
        if err then
            return
        end

        local after = table.concat(vim.api.nvim_buf_get_lines(bufnr, 0, -1, false), '\n') .. '\n'
        local hunks = did_edit and vim.text.diff(before, after, { result_type = 'indices' }) or {}
        local affected = 0

        for _, hunk in ipairs(hunks) do
            -- Pure insertions touch no original lines, so count them against the line they follow
            affected = affected + math.max(hunk[2], 1)
        end

        local msg = affected == 0 and 'No lines reformatted' or string.format('%d lines reformatted', affected, total)

        -- Scheduled so it shows after the "written" message rather than being overwritten by it
        vim.schedule(function()
            vim.notify(msg)
        end)
    end
end

require('conform').setup {
    -- Returning a callback alongside the options is supported but undocumented
    format_on_save = function(bufnr)
        return { timeout_ms = 500, lsp_format = 'fallback' }, report_format_changes(bufnr)
    end,
    formatters_by_ft = {
        lua = { 'stylua' },
        python = { 'ruff_fix', 'ruff_format' },
        markdown = { 'prettier' },
        ['markdown.mdx'] = { 'prettier' },
        json = { 'prettier' },
        jsonc = { 'prettier' },
        toml = { 'taplo' },
    },
    formatters = {
        prettier = {
            prepend_args = {
                '--prose-wrap',
                'always',
                '--print-width',
                '90',
                -- Do not format contents of code blocks
                '--embedded-language-formatting',
                'off',
            },
        },
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

-- Provided by Xcode/Swift toolchain rather than Mason, so only enable where installed
if vim.fn.executable 'sourcekit-lsp' == 1 then
    vim.lsp.config('sourcekit', { filetypes = { 'swift', 'objc', 'objcpp' } })
    vim.lsp.enable 'sourcekit'
end

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
    require('conform').format(nil, report_format_changes(0))
end, { desc = 'Format and apply autofixes (Conform)' })
