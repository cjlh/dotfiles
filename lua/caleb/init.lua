require("caleb.remap")

-- Post-install hook equivalent
vim.api.nvim_create_autocmd('PackChanged', {
    callback = function(ev)
        local name, kind = ev.data.spec.name, ev.data.kind
        if kind == 'delete' then return end

        if name == 'nvim-treesitter' then
            if not ev.data.active then vim.cmd.packadd('nvim-treesitter') end
            vim.cmd('TSUpdate')
        end

        if name == 'telescope-fzf-native.nvim' then
            local path = vim.fn.stdpath('data') .. '/site/pack/core/opt/' .. name
            vim.system({ 'make' }, { cwd = path })
        end
    end,
})

vim.pack.add({
    'https://github.com/nvim-lua/plenary.nvim',
    'https://github.com/nvim-telescope/telescope.nvim',
    'https://github.com/nvim-telescope/telescope-fzf-native.nvim',
    'https://github.com/debugloop/telescope-undo.nvim',
    { src = 'https://github.com/nvim-treesitter/nvim-treesitter', version = 'main' },
    { src = 'https://github.com/ThePrimeagen/harpoon',            version = 'harpoon2' },
    'https://github.com/mason-org/mason.nvim',
    'https://github.com/neovim/nvim-lspconfig',
    'https://github.com/AlexvZyl/nordic.nvim',
    'https://github.com/gelguy/wilder.nvim',
    'https://github.com/nvim-mini/mini.snippets',
    'https://github.com/nvim-mini/mini.completion',
    'https://github.com/tpope/vim-fugitive',
})

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

