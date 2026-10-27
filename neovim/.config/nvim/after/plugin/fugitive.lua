vim.keymap.set('n', '<leader>Gs', function()
    -- vim.cmd [[Git status]]
    vim.cmd 'Git'
end, {
    desc = 'Open git status (fugitive)',
})

vim.keymap.set('n', '<leader>Gd', '<cmd>vert Git diff<CR>', { desc = 'Open git diff in vsplit (fugitive)' })
