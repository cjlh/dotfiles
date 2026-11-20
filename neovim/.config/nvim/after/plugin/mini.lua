local function hide_hidden_dirs(fs_entry)
    return not (fs_entry.fs_type == 'directory' and vim.startswith(fs_entry.name, '.'))
end

local function show_all()
    return true
end

require('mini.files').setup {
    windows = { preview = true, width_preview = 50 },
    content = { filter = hide_hidden_dirs },
}

-- Track the filter ourselves because mini.files doesn't expose the options of the open explorer.
local showing_hidden_dirs = false

-- Switch filters in place to preserve the directory and cursor position.
-- Repeating the same shortcut closes the explorer.
---@param show_hidden_dirs boolean
local function toggle_mini_files(show_hidden_dirs)
    local opts = { content = { filter = show_hidden_dirs and show_all or hide_hidden_dirs } }

    if MiniFiles.get_explorer_state() == nil then
        local buf_name = vim.api.nvim_buf_get_name(0)
        local path = vim.fn.filereadable(buf_name) == 1 and buf_name or vim.fn.getcwd()
        MiniFiles.open(path, true, opts)
        MiniFiles.reveal_cwd()
    elseif showing_hidden_dirs == show_hidden_dirs then
        MiniFiles.close()
        return
    else
        MiniFiles.refresh(opts)
    end

    showing_hidden_dirs = show_hidden_dirs
end

vim.keymap.set('n', '<leader>e', function()
    toggle_mini_files(false)
end, { desc = 'Toggle mini.files' })

vim.keymap.set('n', '<leader>E', function()
    toggle_mini_files(true)
end, { desc = 'Toggle mini.files (show hidden directories)' })

local mini_files_group = vim.api.nvim_create_augroup('user_mini_files', {})

vim.api.nvim_create_autocmd('User', {
    pattern = 'MiniFilesExplorerClose',
    desc = 'Reset hidden directory tracking, since explorers opened by other means use the default filter',
    group = mini_files_group,
    callback = function()
        showing_hidden_dirs = false
    end,
})

vim.api.nvim_create_autocmd('User', {
    pattern = 'MiniFilesBufferCreate',
    desc = 'Add mini.files buffer mappings for <Esc> and <CR>',
    group = mini_files_group,
    callback = function(args)
        local buf_id = args.data.buf_id
        vim.keymap.set('n', '<Esc>', MiniFiles.close, { buffer = buf_id, desc = 'Close mini.files' })
        vim.keymap.set('n', '<CR>', function()
            MiniFiles.go_in { close_on_file = true }
        end, { buffer = buf_id, desc = 'Open file and close mini.files' })
    end,
})

-- LSP completion (built-in completion is opt-in and left disabled)
require('mini.completion').setup {}

-- Only used for nvim-scrollbar diff markers
require('mini.diff').setup {}

-- Expand snippets from LSP completion.
require('mini.snippets').setup {
    mappings = {
        jump_next = '<Tab>',
        jump_prev = '<S-Tab>',
    },
}

-- Completion and autocorrect in command line
require('mini.cmdline').setup {}

-- Delete buffers while preserving window layout
require('mini.bufremove').setup {}

vim.keymap.set('n', '<leader>bd', function()
    if not vim.bo.modified then
        MiniBufremove.delete(0)
        return
    end

    local name = vim.fn.bufname()
    local msg = name == '' and 'Buffer not saved. Are you sure you want to delete it?'
        or ('There are unsaved changes to %q. Are you sure you want to delete the buffer?'):format(name)

    -- Default to No
    if vim.fn.confirm(msg, '&Yes\n&No', 2) == 1 then
        MiniBufremove.delete(0, true)
    end
end, { desc = 'Delete buffer (mini.bufremove)' })

vim.api.nvim_create_autocmd('FileType', {
    pattern = 'snacks_picker_input',
    desc = 'Disable mini.completion for snacks picker',
    group = vim.api.nvim_create_augroup('user_mini', {}),
    command = 'lua vim.b.minicompletion_disable=true',
})
