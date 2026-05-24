require("caleb.remap")

require("config.lazy")

require("lazy").setup({
  spec = {
    { import = "caleb.plugins" },
  },
  -- Configure any other settings here. See the documentation for more details.
  -- colorscheme that will be used when installing plugins.
  install = { colorscheme = { "habamax" } },
  -- automatically check for plugin updates
  checker = { enabled = true },
})

vim.cmd.packadd("nvim.undotree")

vim.o.tabstop = 4 -- A TAB character looks like 4 spaces
vim.o.expandtab = true -- Pressing the TAB key will insert spaces instead of a TAB character
vim.o.softtabstop = 4 -- Number of spaces inserted instead of a TAB character
vim.o.shiftwidth = 4 -- Number of spaces inserted when indenting

vim.o.number = true
-- vim.o.relativenumber = true

vim.opt.wildmode = "longest:full,full"

-- Disable background colour
--                            also "SignColumn"
for _, group in ipairs({ "Normal", "NormalFloat" }) do
  vim.api.nvim_set_hl(0, group, { bg = "none" })
end

