vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- Copy, cut and paste to system clipboard
vim.keymap.set({ "n", "v" }, "<leader>y", '"+y', { desc = "Yank from system clipboard" })
vim.keymap.set({ "n", "v" }, "<leader>x", '"+d', { desc = "Cut from system clipboard" })
vim.keymap.set({ "n", "v" }, "<leader>p", '"+p', { desc = "Paste from system clipboard" })
vim.keymap.set({ "n", "v" }, "<leader>P", '"+P', { desc = "Paste from system clipboard before current" })

-- Delete to blackhole register by default
vim.keymap.set({ "n", "v" }, "d", '"_d', { desc = "Delete to blackhole register" })
vim.keymap.set({ "n", "v" }, "<Del>", '"_x', { desc = "Delete to blackhole register" })

-- Use leader-d for delete to clipboard
vim.keymap.set({ "n", "v" }, "<leader>d", "d", { desc = "Delete to clipboard" })

-- Paste over selected text
vim.keymap.set("x", "p", '"_dP', { desc = "Paste over selected text" })

-- Clear highlights and redraw
vim.keymap.set("n", "<C-L>", function()
    vim.cmd.nohlsearch()
    vim.cmd("redraw")
end, { desc = "Clear highlights" })

-- Move lines up and down in visual mode
vim.keymap.set("v", "J", ":m '>+1<CR>gv=gv", { desc = "Move line down" })
vim.keymap.set("v", "K", ":m '<-2<CR>gv=gv", { desc = "Move line up" })

-- Open LSP definitions in new tab
vim.keymap.set("n", "<C-RightMouse>", function()
    vim.cmd("tab split")
    vim.lsp.buf.definition()
end, { desc = "Open LSP definition in new tab" })

-- Fix InsertLeave not firing
vim.keymap.set("i", "<C-c>", "<Esc>")

vim.keymap.set("n", "<leader>s", ':%s/', { desc = "Begin grep in file" })

