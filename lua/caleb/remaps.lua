vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- Copy, cut and paste to system clipboard
vim.keymap.set({ "n", "v" }, "<leader>y", '"+y')
vim.keymap.set({ "n", "v" }, "<leader>x", '"+d')
vim.keymap.set({ "n", "v" }, "<leader>p", '"+p')
vim.keymap.set({ "n", "v" }, "<leader>P", '"+P')

-- Delete to blackhole register by default
vim.keymap.set({ "n", "v" }, "d", '"_d')
vim.keymap.set({ "n", "v" }, "<Del>", '"_x')
vim.keymap.set({ "n", "v" }, "x", '"_x')

-- Use leader-d for delete to clipboard
vim.keymap.set({ "n", "v" }, "<leader>d", "d")

-- Paste over selected text
vim.keymap.set("x", "p", '"_dP')

-- Clear highlights and redraw
vim.keymap.set("n", "<C-L>", function()
    vim.cmd.nohlsearch()
    vim.cmd("redraw")
end)

-- Move lines up and down in visual mode
vim.keymap.set("v", "J", ":m '>+1<CR>gv=gv")
vim.keymap.set("v", "K", ":m '<-2<CR>gv=gv")

-- Fix InsertLeave not firing
vim.keymap.set("i", "<C-c>", "<Esc>")

vim.keymap.set("n", "<leader>F", vim.lsp.buf.format)

vim.keymap.set("n", "<leader>s", ':%s/')

