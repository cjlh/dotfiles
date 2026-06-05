require('mason').setup()

require('mason-lspconfig').setup {
    ensure_installed = { 'basedpyright', 'ruff', 'lua_ls', 'stylua' },
    automatic_installation = true,
    automatic_enable = false,
}
