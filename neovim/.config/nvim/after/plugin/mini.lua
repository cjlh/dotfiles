-- https://github.com/nvim-mini/mini.nvim/blob/main/readmes/mini-files.md
require('mini.files').setup {
    windows = { preview = true, width_preview = 50 },
    content = {
        -- Hide hidden directories, but keep hidden files
        filter = function(fs_entry)
            return not (fs_entry.fs_type == 'directory' and vim.startswith(fs_entry.name, '.'))
        end,
    },
}

vim.keymap.set('n', '<leader>e', function()
    -- close() returns a falsy value when no explorer is open
    if not MiniFiles.close() then
        local buf_name = vim.api.nvim_buf_get_name(0)
        local path = vim.fn.filereadable(buf_name) == 1 and buf_name or vim.fn.getcwd()
        MiniFiles.open(path)
        MiniFiles.reveal_cwd()
    end
end, { desc = 'Toggle mini.files' })

vim.api.nvim_create_autocmd('User', {
    pattern = 'MiniFilesBufferCreate',
    desc = 'Close mini.files with <Esc>',
    group = vim.api.nvim_create_augroup('user_mini_files', {}),
    callback = function(args)
        vim.keymap.set('n', '<Esc>', MiniFiles.close, { buffer = args.data.buf_id, desc = 'Close mini.files' })
    end,
})

-- LSP completion (built-in completion is opt-in and left disabled)
require('mini.completion').setup {}

-- Only used for nvim-scrollbar diff markers
require('mini.diff').setup {}

-- Only used for LSP snippets currently
require('mini.snippets').setup {
    mappings = {
        jump_next = '<Tab>',
        jump_prev = '<S-Tab>',
    },
}

-- Completion and autocorrect in command line
require('mini.cmdline').setup {}

vim.api.nvim_create_autocmd('FileType', {
    pattern = 'snacks_picker_input',
    desc = 'Disable mini.completion for snacks picker',
    group = vim.api.nvim_create_augroup('user_mini', {}),
    command = 'lua vim.b.minicompletion_disable=true',
})
