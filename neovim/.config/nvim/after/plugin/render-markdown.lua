local render_markdown = require 'render-markdown'

render_markdown.setup {
    -- Keep markup characters visible so lines don't shift when the cursor enters them
    win_options = { conceallevel = { rendered = 0 } },
    -- Nothing is hidden any more, so there's nothing to reveal on the cursor line
    anti_conceal = { enabled = false },
    -- Do not overwrite heading # symbols
    heading = { icons = {} },
    code = {
        -- Don't draw the border/language label over the ``` fences
        border = 'none',
        language = false,
    },
}

vim.keymap.set('n', '<leader>M', render_markdown.buf_toggle, { desc = 'Toggle markdown rendering (render-markdown)' })
