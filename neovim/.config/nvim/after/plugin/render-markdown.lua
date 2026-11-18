local render_markdown = require 'render-markdown'

render_markdown.setup {
    pipe_table = { enabled = true },
    checkbox = { enabled = true },

    -- Block quote colours, plus callouts, which are drawn as part of block quotes
    quote = { enabled = true },

    -- Conceal link destinations so only the link text shows (level 3 also hides replaced characters)
    win_options = { conceallevel = { rendered = 2 } },

    -- Match the raw markdown list marker colour rather than the plugin default of Normal
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
