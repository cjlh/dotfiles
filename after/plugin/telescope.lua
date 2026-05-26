local builtin = require('telescope.builtin')

require("telescope").setup({
    extensions = {
        undo = {
            side_by_side = true,
            -- layout_strategy = "vertical",
            -- layout_config = { preview_height = 0.8 },
            initial_mode = "normal",
        },
    },
})

require("telescope").load_extension("undo")

vim.keymap.set('n', '<leader>ff', builtin.find_files, { desc = 'Telescope find files' })
vim.keymap.set('n', '<leader>fg', builtin.live_grep, { desc = 'Telescope live grep' })
vim.keymap.set('n', '<leader>fb', builtin.buffers, { desc = 'Telescope buffers' })
vim.keymap.set('n', '<leader>fh', builtin.help_tags, { desc = 'Telescope help tags' })

vim.keymap.set('n', '<leader>u', '<cmd>Telescope undo<cr>', { desc = 'undo history' })

-- Below from https://www.youtube.com/watch?v=w7i4amO_zaE

vim.keymap.set('n', '<C-p>', builtin.git_files, { desc = 'Telescope find git files' })

-- vim.keymap.set('n', '<leader>ps', function()
--     builtin.grep_string({ search = vim.fn.input("Grep > ") });
-- end)

