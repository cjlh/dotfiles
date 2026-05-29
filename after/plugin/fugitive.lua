vim.keymap.set('n', '<leader>Gs', function()
    vim.cmd [[Git status]]
end, {
    desc = 'Open git status (fugitive)',
})
