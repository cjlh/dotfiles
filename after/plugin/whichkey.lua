local whichkey = require 'which-key'

whichkey.setup {
    delay = 2500,
    win = {
        border = 'rounded',
    },
}

vim.keymap.set('n', '<leader>?', function()
    whichkey.show {
        global = true,
    }
end, { desc = 'View global keymaps (which-key)' })
