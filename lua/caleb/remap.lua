vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- Copy, cut and paste to system clipboard
vim.keymap.set({ "n", "v" }, "<leader>y", '"+y')
vim.keymap.set({ "n", "v" }, "<leader>x", '"+d')
vim.keymap.set({ "n", "v" }, "<leader>p", '"+p')
vim.keymap.set({ "n", "v" }, "<leader>P", '"+P')

-- Delete to blackhole register by default
vim.keymap.set({ "n", "v" }, "d", '"_d')
vim.keymap.set({ "n", "v" }, "<leader>d", "d")

vim.keymap.set("n", "<C-L>", function()
    vim.cmd.nohlsearch()
    vim.cmd("redraw")
end)

vim.keymap.set("n", "<leader>F", vim.lsp.buf.format)

vim.keymap.set("n", "<leader>s", ':%s/')

