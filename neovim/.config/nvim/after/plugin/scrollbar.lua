local scrollbar = require 'scrollbar'

scrollbar.setup {
    providers = {
        mini_diff = true,
        lsp_semantic_tokens = true,
    },
    scrollbar = {
        enabled = false,
        thumb = {
            -- Make thumb visible against a transparent background
            highlight = { bg = '#3c3c4a' },
        },
    },
    minimap = {
        enabled = true,
        preset = 'compact',
        scale = 'fit',
        placement = { relative = 'editor' },
    },
}

vim.keymap.set('n', '<leader>m', require('scrollbar.minimap').toggle, { desc = 'Toggle minimap scrollbar' })
