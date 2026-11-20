require('codediff').setup {}

vim.api.nvim_create_autocmd('User', {
    pattern = 'CodeDiffOpen',
    group = vim.api.nvim_create_augroup('user_codediff', { clear = true }),
    callback = function(event)
        if event.data.layout ~= 'inline' or event.data.mode ~= 'explorer' then
            return
        end
        local explorer = require('codediff.ui.lifecycle').get_panel_view(event.data.tabpage)
        if explorer and not explorer.is_hidden then
            require('codediff.ui.explorer').toggle_visibility(explorer)
        end
    end,
})

vim.keymap.set('n', '<leader>gd', '<cmd>CodeDiff<CR>', { desc = 'Toggle diff view (codediff)' })
vim.keymap.set('n', '<leader>gi', '<cmd>CodeDiff --inline<CR>', { desc = 'Open inline diff without sidebar (codediff)' })
vim.keymap.set('n', '<leader>gf', '<cmd>CodeDiff history %<CR>', { desc = 'Open current file history (codediff)' })
