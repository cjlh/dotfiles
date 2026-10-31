-- https://github.com/nvim-mini/mini.nvim/blob/e7538b549361c9ac8416a07b0223ce03c508bfe7/readmes/mini-completion.md

-- LSP completion (built-in completion is opt-in and left disabled)
require('mini.completion').setup {}

-- Only used for LSP snippets currently
require('mini.snippets').setup {
    mappings = {
        jump_next = '<Tab>',
        jump_prev = '<S-Tab>',
    },
}

-- Completion and autocorrect in command line
require('mini.cmdline').setup {}

vim.api.nvim_create_autocmd('FileType', {
    pattern = 'snacks_picker_input',
    desc = 'Disable mini.completion for snacks picker',
    group = vim.api.nvim_create_augroup('user_mini', {}),
    command = 'lua vim.b.minicompletion_disable=true',
})
