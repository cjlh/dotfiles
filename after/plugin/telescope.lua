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

vim.keymap.set('n', '<leader>u', '<cmd>Telescope undo<cr>', { desc = 'undo history' })

