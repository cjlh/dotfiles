-- To remove a plugin, delete its spec below, restart, then run `:packdel ++all`

-- Post-install hook equivalent
vim.api.nvim_create_autocmd('PackChanged', {
    callback = function(ev)
        local name, kind = ev.data.spec.name, ev.data.kind
        if kind == 'delete' then
            return
        end

        if name == 'nvim-treesitter' then
            if not ev.data.active then
                vim.cmd.packadd 'nvim-treesitter'
            end
            vim.cmd 'TSUpdate'
        end
    end,
})

-- Show keymap
vim.pack.add {
    'https://github.com/folke/which-key.nvim',
}

-- Mini
vim.pack.add {
    { src = 'https://github.com/nvim-mini/mini.nvim', version = 'stable' },
}

-- Language support
vim.pack.add {
    { src = 'https://github.com/nvim-treesitter/nvim-treesitter', version = 'main' },
    'https://github.com/mason-org/mason.nvim',
    'https://github.com/mason-org/mason-lspconfig.nvim',
    'https://github.com/neovim/nvim-lspconfig',
    'https://github.com/stevearc/conform.nvim',
}

-- Themes
vim.pack.add {
    -- 'https://github.com/AlexvZyl/nordic.nvim',
    -- 'https://github.com/Mofiqul/vscode.nvim',
    'https://github.com/vague-theme/vague.nvim',
}

-- Git
vim.pack.add {
    'https://github.com/tpope/vim-fugitive',
    'https://github.com/sindrets/diffview.nvim',
    'https://github.com/lewis6991/gitsigns.nvim',
}

-- Support viewing images
vim.pack.add {
    'https://github.com/folke/snacks.nvim',
    'https://github.com/nvim-tree/nvim-web-devicons',
}
