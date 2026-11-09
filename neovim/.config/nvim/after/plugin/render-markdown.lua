local render_markdown = require 'render-markdown'

render_markdown.setup {}

vim.keymap.set('n', '<leader>M', render_markdown.buf_toggle, { desc = 'Toggle markdown rendering (render-markdown)' })
