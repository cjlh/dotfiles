vim.keymap.set("n", "<leader>?", function() require("which-key").show({
    global = true
}) end, { desc = "View global keymaps (which-key)" })

