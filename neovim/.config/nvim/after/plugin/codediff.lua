require('codediff').setup {}

vim.keymap.set('n', '<leader>gd', '<cmd>CodeDiff<CR>', { desc = 'Toggle diff view (codediff)' })
vim.keymap.set('n', '<leader>gf', '<cmd>CodeDiff history %<CR>', { desc = 'Open current file history (codediff)' })
