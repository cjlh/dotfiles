local gitsigns = require 'gitsigns'

gitsigns.setup {
    -- signs = {
    --     add = { text = '┃' },
    --     change = { text = '┃' },
    --     delete = { text = '_' },
    --     topdelete = { text = '‾' },
    --     changedelete = { text = '~' },
    --     untracked = { text = '┆' },
    -- },
    -- signs_staged = {
    --     add = { text = '┃' },
    --     change = { text = '┃' },
    --     delete = { text = '_' },
    --     topdelete = { text = '‾' },
    --     changedelete = { text = '~' },
    --     untracked = { text = '┆' },
    -- },
    attach_to_untracked = true,
    current_line_blame_formatter = '<abbrev_sha> <author>, <author_time:%R> - <summary>',
    current_line_blame_opts = {
        use_focus = false,
        delay = vim.o.updatetime,
    },
}

vim.keymap.set(
    'n',
    '<leader>Gb',
    gitsigns.toggle_current_line_blame,
    { desc = 'Toggle git blame annotations (gitsigns)' }
)
vim.keymap.set('n', '<leader>GB', gitsigns.blame, { desc = 'Open git blame sidebar (gitsigns)' })

vim.keymap.set('n', '<leader>Gp', gitsigns.preview_hunk, { desc = 'Preview current hunk (gitsigns)' })

vim.keymap.set('n', '<leader>Gh', gitsigns.stage_hunk, { desc = 'Stage current hunk (gitsigns)' })
vim.keymap.set('n', '<leader>GH', gitsigns.reset_hunk, { desc = 'Reset current hunk (gitsigns)' })

vim.keymap.set('v', '<leader>Gh', function()
    gitsigns.stage_hunk { vim.fn.line '.', vim.fn.line 'v' }
end, { desc = 'Stage selected hunks (gitsigns)' })

vim.keymap.set('v', '<leader>GH', function()
    gitsigns.reset_hunk { vim.fn.line '.', vim.fn.line 'v' }
end, { desc = 'Unstage selected hunks (gitsigns)' })

vim.keymap.set('n', '<leader>Ga', gitsigns.stage_buffer, { desc = 'Stage current buffer (gitsigns)' })
vim.keymap.set('n', '<leader>Gr', gitsigns.reset_buffer, { desc = 'Reset current buffer (gitsigns)' })
