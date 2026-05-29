vim.keymap.set('n', '<leader>Gd', function()
    if next(require('diffview.lib').views) == nil then
        vim.cmd [[DiffviewOpen --imply-local]]
    else
        vim.cmd [[DiffviewClose]]
    end
end, {
    desc = 'Toggle diff view (diffview)',
})
