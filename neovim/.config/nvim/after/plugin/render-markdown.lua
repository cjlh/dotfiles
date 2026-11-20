local render_markdown = require 'render-markdown'

render_markdown.setup {
    pipe_table = { enabled = true },
    checkbox = { enabled = true },
    quote = { enabled = true },

    -- Hide link destinations while keeping replacement characters visible
    win_options = { conceallevel = { rendered = 2 } },

    -- Keep rendered bullets the same colour as the original list markers
    bullet = { enabled = true, highlight = '@markup.list' },

    -- Render only plain links
    link = {
        enabled = true,
        footnote = { enabled = false },
        wiki = { enabled = false },
    },

    heading = { enabled = false },
    paragraph = { enabled = false },
    code = { enabled = false },
    dash = { enabled = false },
    inline_highlight = { enabled = false },
    sign = { enabled = false },
    indent = { enabled = false },
    html = { enabled = false },
    latex = { enabled = false },
    yaml = { enabled = false },
}

vim.keymap.set('n', '<leader>M', render_markdown.buf_toggle, { desc = 'Toggle markdown rendering (render-markdown)' })
