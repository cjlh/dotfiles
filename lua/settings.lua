vim.opt.tabstop = 4 -- Tab char looks like 4 spaces
vim.opt.expandtab = true -- Tab key inserts spaces instead of a tab char
vim.opt.softtabstop = 4 -- Number of spaces inserted instead of tab char
vim.opt.shiftwidth = 4 -- Number of spaces inserted when indenting

vim.opt.smartindent = true

vim.opt.swapfile = false
vim.opt.backup = false
vim.opt.undodir = os.getenv 'HOME' .. '/.vim/undodir'
vim.opt.undofile = true

vim.opt.number = true
-- vim.opt.relativenumber = true

-- Show whitespace
vim.opt.list = true
vim.opt.listchars = { lead = '⋅', trail = '⋅', tab = '  ↦' }

vim.opt.ignorecase = true
vim.opt.smartcase = true

vim.opt.hlsearch = true
vim.opt.incsearch = true

vim.opt.signcolumn = 'yes'
vim.opt.colorcolumn = '90'

vim.opt.scrolloff = 8

vim.opt.splitbelow = true
vim.opt.splitright = true

vim.opt.termguicolors = true

vim.opt.completeopt = { 'menu', 'menuone', 'noselect' }
vim.opt.wildmenu = true
vim.opt.wildmode = 'longest:full,full'
vim.opt.wildignore:append '.DS_Store'

-- Enable @ characters in filenames
vim.opt.isfname:append '@-@'

vim.opt.winborder = 'rounded'
vim.opt.pumborder = 'rounded'
vim.opt.pumblend = 0

vim.opt.updatetime = 50

vim.api.nvim_set_hl(0, 'Pmenu', { bg = 'none' })
vim.api.nvim_set_hl(0, 'PmenuBorder', { bg = 'none' })

-- Disable background colour
for _, group in ipairs { 'Normal', 'NormalFloat', 'SignColumn' } do
    vim.api.nvim_set_hl(0, group, { bg = 'none' })
end

-- Disable welcome message
vim.opt.shortmess:append 'I'
