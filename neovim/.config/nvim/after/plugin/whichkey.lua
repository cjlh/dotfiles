local whichkey = require 'which-key'

whichkey.setup {
    delay = 2500,
    -- Use explicit prefix triggers for visual mode as otherwise whichkey unexpectedly hides
    -- mode indicator (e.g. "-- VISUAL --").
    triggers = {
        { '<auto>', mode = 'nso' },
        { '<leader>', mode = 'x' },
        { 'g', mode = 'x' },
        { 'z', mode = 'x' },
        { '[', mode = 'x' },
        { ']', mode = 'x' },
        { '<C-w>', mode = 'x' },
    },
    win = {
        border = 'rounded',
    },
}

vim.keymap.set('n', '<leader>?', function()
    whichkey.show {
        global = true,
    }
end, { desc = 'View global keymaps (which-key)' })
