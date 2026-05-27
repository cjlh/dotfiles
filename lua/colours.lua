require('vague').setup {
    colors = {
        hint = '#aeaed1',
    },
}

vim.cmd.colorscheme 'vague'

vim.api.nvim_set_hl(0, 'Pmenu', { bg = 'none' })
vim.api.nvim_set_hl(0, 'PmenuBorder', { bg = 'none' })

-- Disable background colour
for _, group in ipairs { 'Normal', 'NormalFloat', 'SignColumn' } do
    vim.api.nvim_set_hl(0, group, { bg = 'none' })
end
