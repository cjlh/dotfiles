-- https://github.com/nvim-mini/mini.nvim/blob/e7538b549361c9ac8416a07b0223ce03c508bfe7/readmes/mini-completion.md

require('mini.completion').setup({
  delay = { completion = 100, info = 1000, signature = 500 },
})

require('mini.snippets').setup({})

