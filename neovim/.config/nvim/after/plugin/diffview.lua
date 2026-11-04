vim.keymap.set('n', '<leader>GD', function()
    if next(require('diffview.lib').views) == nil then
        vim.cmd [[DiffviewOpen --imply-local]]
    else
        vim.cmd [[DiffviewClose]]
    end
end, {
    desc = 'Toggle diff view (diffview)',
})

vim.keymap.set('n', '<leader>Gf', '<cmd>DiffviewFileHistory %<CR>', { desc = 'Open current file history (diffview)' })
