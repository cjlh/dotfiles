-- https://www.reddit.com/r/neovim/comments/1r92p2y/small_utility_for_listing_and_deleting_inactive/
vim.api.nvim_create_user_command('Packages', function()
    vim.pack.update(nil, { offline = true })
end, { desc = 'Manage installed packages - `gra` to remove' })
