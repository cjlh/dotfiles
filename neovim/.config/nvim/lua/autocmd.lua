vim.api.nvim_create_autocmd('BufReadPost', {
    desc = 'Always jump to last known cursor position when opening file',
    callback = function(ev)
        local ft = vim.filetype.match { buf = ev.buf } or ''
        if
            ft:match 'commit'
            or vim.tbl_contains({ 'gitrebase', 'xxd' }, ft)
            or vim.wo.diff -- Note this is diff mode (`nvim -d`) and not the diff filetype
            or vim.fs.basename(ev.file) == 'addp-hunk-edit.diff'
        then
            return
        end
        local mark = vim.api.nvim_buf_get_mark(0, '"')
        local line_count = vim.api.nvim_buf_line_count(0)
        if mark[1] > 0 and mark[1] <= line_count then
            vim.api.nvim_win_set_cursor(0, mark)
            vim.schedule(function()
                Snacks.scroll.disable()
                vim.cmd 'normal! zz'
                Snacks.scroll.enable()
            end)
        end
    end,
})
