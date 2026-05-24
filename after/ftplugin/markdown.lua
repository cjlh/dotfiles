local colorscheme = "nordic"

local ok, _ = pcall(vim.api.nvim_command, "colorscheme " .. colorscheme)

if ok then
    for _, group in ipairs({ "Normal", "NormalFloat" }) do
      vim.api.nvim_set_hl(0, group, { bg = "none" })
    end 
else
    print("error setting colorscheme")
end

