require('mason').setup()

require('mason-lspconfig').setup {
    ensure_installed = { 'basedpyright', 'ruff', 'lua_ls' },
    automatic_installation = true,
    automatic_enable = false,
}

-- Install formatters via registry as they're not supported by `ensure_installed`
local registry = require 'mason-registry'
registry.refresh(function()
    for _, name in ipairs { 'stylua', 'prettier' } do
        local ok, pkg = pcall(registry.get_package, name)
        if ok and not pkg:is_installed() then
            pkg:install()
        end
    end
end)
