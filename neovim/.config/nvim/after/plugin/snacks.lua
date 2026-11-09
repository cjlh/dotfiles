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

require('snacks').setup {
    image = {},
    scroll = {},
    words = {
        debounce = vim.o.updatetime,
    },
    terminal = {
        win = {
            border = 'rounded',
            position = 'float',
        },
    },
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
            grep = {
                hidden = true,
                ignored = false,
                exclude = exclude_dirs,
            },
            explorer = {
                win = {
                    input = {
                        title = 'Explorer',
                    },
                },
                layout = {
                    hidden = { 'input' },
                    auto_hide = { 'input' },
                },
                finder = function(opts, ctx)
                    opts.exclude = ctx.filter:is_empty() and {} or exclude_dirs
                    return require('snacks.picker.source.explorer').explorer(opts, ctx)
                end,
            },
            projects = {
                dev = { '~/Work', '~/Documents', '~/Projects', '/tmp' },
                patterns = {
                    -- Snacks defaults
                    '.git',
                    '_darcs',
                    '.hg',
                    '.bzr',
                    '.svn',
                    'package.json',
                    'Makefile',
                    -- Python
                    'pyproject.toml',
                    'setup.py',
                    'setup.cfg',
                    'requirements.txt',
                    'Pipfile',
                    'uv.lock',
                    'poetry.lock',
                    '.venv',
                    'venv',
                    -- Agent sessions
                    '.claude',
                },
            },
        },
    },
    explorer = {
        -- replace_netrw = true,
    },
}

local function toggle_explorer()
    local explorers = Snacks.picker.get { source = 'explorer' }
    if #explorers > 0 then
        for _, picker in ipairs(explorers) do
            picker:close()
        end
    else
        Snacks.explorer.open()
    end
end

vim.api.nvim_create_user_command('Explorer', toggle_explorer, { desc = 'Toggle the Snacks explorer' })

vim.keymap.set('n', '<leader>e', toggle_explorer, { desc = 'Toggle explorer (Snacks)' })

local function toggle_terminal()
    Snacks.terminal.toggle()
end

vim.keymap.set({ 'n', 't' }, '<C-/>', toggle_terminal, { desc = 'Toggle terminal (Snacks)' })
vim.keymap.set('n', '<leader>/', toggle_terminal, { desc = 'Toggle terminal (Snacks)' })

vim.keymap.set('n', '<leader><leader>', function()
    Snacks.picker.files()
end, { desc = 'Open file picker (Snacks)' })

local function files_and_dirs(cwd)
    Snacks.picker.files {
        cwd = cwd,
        -- Added to the default `fd --type f --type l`; only list immediate children
        args = { '--type', 'd', '--max-depth', '1' },
        transform = function(item)
            -- fd suffixes directories with `/`
            item.dir = item.file:sub(-1) == '/'
            item.group = item.dir and 2 or 1 -- List directories after sibling files
        end,
        matcher = { sort_empty = true },
        sort = { fields = { 'score:desc', 'group', 'file' } },
        confirm = function(picker, item)
            if item and item.dir then
                picker:close()
                files_and_dirs(Snacks.picker.util.path(item))
            else
                picker:action 'jump'
            end
        end,
    }
end

vim.keymap.set('n', '<leader>f', function()
    files_and_dirs(vim.fn.expand '%:p:h')
end, { desc = "Open file and directory picker in current buffer's directory (Snacks)" })

vim.keymap.set('n', '<C-space>', function()
    Snacks.picker.grep()
end, { desc = 'Open file search (Snacks)' })

vim.keymap.set('n', '<leader>gu', function()
    Snacks.picker.git_status {
        title = 'Unstaged changes',
        ignored = false, -- Override global `picker.ignored`, which would list `!!` entries
        transform = function(item)
            -- `item.status` is the two-char porcelain XY code; Y is the worktree status
            if item.status == '??' then
                -- Untracked: drop hidden files and anything inside hidden dirs
                if item.file:match '^%.' or item.file:match '/%.' then
                    return false
                end
                item.group = 2
            elseif item.status:sub(2, 2) ~= ' ' then
                item.group = 1 -- Tracked with unstaged worktree changes
            else
                return false -- Only staged changes
            end
        end,
        matcher = { sort_empty = true },
        sort = { fields = { 'score:desc', 'group', 'file' } },
    }
end, { desc = 'Open unstaged and untracked git files (Snacks)' })

vim.keymap.set('n', '<leader>u', function()
    Snacks.picker.undo()
end, { desc = 'Undo history (Snacks)' })

local function recent_exclude_paths()
    local cwd = vim.uv.cwd()
    local excludes = {}

    for _, p in ipairs(exclude_dirs) do
        excludes[cwd .. string.format('/%s', p)] = false
    end

    return excludes
end

vim.keymap.set('n', '<leader>rf', function()
    Snacks.picker.recent {
        limit = 50, -- Limit applies pre-filter
        filter = {
            cwd = true,
            paths = recent_exclude_paths(),
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

vim.api.nvim_create_autocmd('QuickFixCmdPost', {
    desc = 'Open builtin QuickFix commands using Snacks.picker',
    pattern = 'cgetexpr,cexpr,grep,grepadd,make,vimgrep,vimgrepadd',
    callback = function()
        Snacks.picker.qflist()
    end,
})

vim.keymap.set('n', 'grr', function()
    Snacks.picker.lsp_references()
end, { desc = 'Open LSP references (Snacks)' })

vim.keymap.set('n', 'gri', function()
    Snacks.picker.lsp_implementations()
end, { desc = 'Open LSP implementations (Snacks)' })

vim.keymap.set('n', 'grt', function()
    Snacks.picker.lsp_type_definitions()
end, { desc = 'Open LSP type definitions (Snacks)' })

vim.keymap.set('n', 'gd', function()
    Snacks.picker.lsp_definitions()
end, { desc = 'Open LSP definitions (Snacks)' })

vim.keymap.set('n', 'gD', function()
    Snacks.picker.lsp_declarations()
end, { desc = 'Open LSP declarations (Snacks)' })

vim.keymap.set('n', 'gO', function()
    Snacks.picker.lsp_symbols()
end, { desc = 'Open LSP document symbols (Snacks)' })

-- No Neovim default for the following

vim.keymap.set('n', '<leader>ci', function()
    Snacks.picker.lsp_incoming_calls()
end, { desc = 'Open LSP incoming calls (Snacks)' })

vim.keymap.set('n', '<leader>co', function()
    Snacks.picker.lsp_outgoing_calls()
end, { desc = 'Open outgoing LSP calls (Snacks)' })

vim.keymap.set('n', ']]', function()
    Snacks.words.jump(vim.v.count1)
end, { desc = 'Jump to next LSP reference (Snacks)' })

vim.keymap.set('n', '[[', function()
    Snacks.words.jump(-vim.v.count1)
end, { desc = 'Jump to previous LSP reference (Snacks)' })
