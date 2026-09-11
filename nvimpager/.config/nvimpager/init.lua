local nvim_data = vim.fs.joinpath(vim.env.XDG_DATA_HOME or vim.fs.joinpath(vim.env.HOME, ".local", "share"), "nvim")

vim.opt.runtimepath:append(vim.fs.joinpath(nvim_data, "site/pack/core/opt/vague.nvim"))
dofile(vim.fn.expand("~/.config/nvim/lua/colours.lua"))

dofile(vim.fn.expand("~/.config/nvim/lua/options.lua"))
dofile(vim.fn.expand("~/.config/nvim/lua/remaps.lua"))
