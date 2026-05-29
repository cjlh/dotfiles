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
}

vim.keymap.set('n', '<leader>Ga', gitsigns.stage_buffer)
vim.keymap.set('n', '<leader>Gr', gitsigns.reset_buffer)

vim.keymap.set('n', '<leader>Gp', gitsigns.preview_hunk)
vim.keymap.set('n', '<leader>Gb', gitsigns.toggle_current_line_blame)

vim.keymap.set('n', '<leader>Gh', gitsigns.stage_hunk)
vim.keymap.set('n', '<leader>GH', gitsigns.reset_hunk)

vim.keymap.set('v', '<leader>Gh', function()
    gitsigns.stage_hunk { vim.fn.line '.', vim.fn.line 'v' }
end)

vim.keymap.set('v', '<leader>GH', function()
    gitsigns.reset_hunk { vim.fn.line '.', vim.fn.line 'v' }
end)
