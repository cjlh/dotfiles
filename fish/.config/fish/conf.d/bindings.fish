# Key bindings

# Open nvim in the current directory, keeping the current contents of the command line
bind alt-shift-enter 'nvim .; commandline -f repaint'

# Edit current command in default editor
bind ctrl-g edit_command_buffer

# Toggle between the prompt and suspended jobs with ctrl-z
bind ctrl-z __fish_resume_job
bind alt-z undo
bind alt-shift-z redo
