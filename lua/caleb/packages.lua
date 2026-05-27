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

-- Show keymap
vim.pack.add({
    'https://github.com/folke/which-key.nvim',
})

-- Telescope
vim.pack.add({
    'https://github.com/nvim-lua/plenary.nvim',
    'https://github.com/nvim-telescope/telescope.nvim',
    'https://github.com/nvim-telescope/telescope-fzf-native.nvim',
    'https://github.com/debugloop/telescope-undo.nvim',
})

-- Mini
vim.pack.add({
    { src = 'https://github.com/nvim-mini/mini.snippets',  version = 'stable' },
    { src = 'https://github.com/nvim-mini/mini.completion', version = 'stable' },
})

-- Language support
vim.pack.add({
    { src = 'https://github.com/nvim-treesitter/nvim-treesitter', version = 'main' },
    'https://github.com/mason-org/mason.nvim',
    'https://github.com/neovim/nvim-lspconfig',
})

-- Themes
vim.pack.add({
    'https://github.com/AlexvZyl/nordic.nvim',
})

-- File management
vim.pack.add({
    { src = 'https://github.com/ThePrimeagen/harpoon',            version = 'harpoon2' },
    'https://github.com/gelguy/wilder.nvim',
    'https://github.com/tpope/vim-fugitive',
})

-- Support viewing images
vim.pack.add({
    'https://github.com/folke/snacks.nvim',
    'https://github.com/nvim-tree/nvim-web-devicons',
})

