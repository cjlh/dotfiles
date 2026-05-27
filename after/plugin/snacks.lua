require('snacks').setup({
    image = {},
    picker = {},
    explorer = {
        replace_netrw = true,
        trash = true,
    },
})

vim.keymap.set("n", "<leader><leader>", function() Snacks.picker.files() end)
vim.keymap.set("n", "<leader>e", function() Snacks.explorer() end)
vim.keymap.set("n", "<C-space>", function() Snacks.picker.grep() end)

