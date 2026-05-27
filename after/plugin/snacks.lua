require("snacks").setup({
    image = {},
    picker = {
        hidden = true,
        ignored = true,
        sources = {
            files = {
                hidden = true,
                ignored = false,
                show_empty = true,
            },
            explorer = {
                win = {
                    border = "bottom",
                    input = {
                        title = "Explorer",
                    },
                },
            },
        },
    },
    explorer = {
        replace_netrw = true,
    },
})

vim.keymap.set("n", "<leader><leader>", function()
    Snacks.picker.files()
end, { desc = "Open file picker (Snacks)" })

vim.keymap.set("n", "<leader>e", function()
    Snacks.explorer()
end, { desc = "Open explorer (Snacks)" })

vim.keymap.set("n", "<C-space>", function()
    Snacks.picker.grep()
end, { desc = "Open file search (Snacks)" })
