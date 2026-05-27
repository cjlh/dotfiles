vim.keymap.set('n', '<leader>gs', function()
    vim.cmd [[Git status]]
end, {
    desc = 'Open git status (fugitive)',
})
