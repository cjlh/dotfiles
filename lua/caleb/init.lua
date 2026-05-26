require("caleb.remap")
require("caleb.packages")

vim.o.tabstop = 4 -- A TAB character looks like 4 spaces
vim.o.expandtab = true -- Pressing the TAB key will insert spaces instead of a TAB character
vim.o.softtabstop = 4 -- Number of spaces inserted instead of a TAB character
vim.o.shiftwidth = 4 -- Number of spaces inserted when indenting

vim.o.number = true
-- vim.o.relativenumber = true

vim.o.ignorecase = true
vim.o.smartcase = true
vim.o.hlsearch = true
vim.o.incsearch = true

vim.wo.scrolloff = 8

vim.o.splitbelow = true
vim.o.splitright = true

vim.o.termguicolors = true

vim.opt.completeopt = { "menu", "menuone", "noselect" }
vim.o.wildmenu = true
vim.opt.wildmode = "longest:full,full"

vim.o.winborder = "rounded"
vim.o.pumborder = "rounded"
vim.o.pumblend = 0

vim.api.nvim_set_hl(0, 'Pmenu', { bg = 'NONE' })
vim.api.nvim_set_hl(0, 'PmenuBorder', { bg = 'NONE' })

-- Disable background colour
for _, group in ipairs({ "Normal", "NormalFloat", "SignColumn" }) do
  vim.api.nvim_set_hl(0, group, { bg = "none" })
end

