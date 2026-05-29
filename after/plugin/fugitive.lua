vim.keymap.set('n', '<leader>Gs', function()
    -- vim.cmd [[Git status]]
    vim.cmd 'Git'
end, {
    desc = 'Open git status (fugitive)',
})
