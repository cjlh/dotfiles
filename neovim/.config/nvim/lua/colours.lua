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
    local hl = vim.api.nvim_get_hl(0, { name = group, link = false })
    hl.bg = nil
    vim.api.nvim_set_hl(0, group, hl)
end
