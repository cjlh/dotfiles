local exclude_dirs = {
    '.DS_Store/',
    '.git/',
    'node_modules/',
    '__pycache__/',
    '.pytest_cache/',
    '.ruff_cache/',
    '.venv/',
    'venv/',
    'dist/',
    'build/',
    'target/',
}

local search_exclude_transform = function(item, ctx)
    if ctx.filter:is_empty() then
        return
    end
    local path = item.file or ''
    for _, dir in ipairs(exclude_dirs) do
        local name = dir:gsub('/+$', '')
        if path:find('/' .. name .. '/', 1, true) or path:sub(-(#name + 1)) == '/' .. name then
            return false
        end
    end
end

require('snacks').setup {
    image = {},
    scroll = {},
    picker = {
        hidden = true,
        ignored = true,
        sources = {
            files = {
                hidden = true,
                ignored = false,
                show_empty = true,
                exclude = exclude_dirs,
            },
            explorer = {
                win = {
                    border = 'bottom',
                    input = {
                        title = 'Explorer',
                    },
                },
                transform = search_exclude_transform,
            },
        },
    },
    explorer = {
        replace_netrw = true,
    },
}

vim.keymap.set('n', '<leader><leader>', function()
    Snacks.picker.files()
end, { desc = 'Open file picker (Snacks)' })

vim.keymap.set('n', '<leader>e', function()
    Snacks.explorer()
end, { desc = 'Open explorer (Snacks)' })

vim.keymap.set('n', '<C-space>', function()
    Snacks.picker.grep()
end, { desc = 'Open file search (Snacks)' })

local recent_exclude_paths = (function()
    local cwd = vim.loop.cwd()
    local excludes = {}

    for _, p in ipairs(exclude_dirs) do
        excludes[cwd .. string.format('/%s', p)] = false
    end

    return excludes
end)()

vim.keymap.set('n', '<leader>rf', function()
    Snacks.picker.recent {
        limit = 50, -- Limit applies pre-filter
        filter = {
            cwd = true,
            paths = recent_exclude_paths,
            -- Filter out entries which aren't readable files
            filter = function(item)
                local file = item.file
                return file ~= nil and file ~= '' and not file:match '^%w[%w+.-]*://' and vim.fn.filereadable(file) == 1
            end,
        },
    }
end, { desc = 'Open recent project files (Snacks)' })

vim.keymap.set('n', '<leader>rp', function()
    Snacks.picker.projects {}
end, { desc = 'Open recent projects (Snacks)' })

vim.api.nvim_create_autocmd('QuitPre', {
    desc = 'Quit Neovim when only the Snacks explorer remains',
    callback = function()
        local snacks_wins, floating_wins = {}, {}
        local wins = vim.api.nvim_list_wins()
        for _, win in ipairs(wins) do
            local ft = vim.bo[vim.api.nvim_win_get_buf(win)].filetype
            if ft:find '^snacks_' then
                table.insert(snacks_wins, win)
            elseif vim.api.nvim_win_get_config(win).relative ~= '' then
                table.insert(floating_wins, win)
            end
        end
        if #wins - #floating_wins - #snacks_wins == 1 then
            for _, win in ipairs(snacks_wins) do
                pcall(vim.api.nvim_win_close, win, true)
            end
        end
    end,
})
