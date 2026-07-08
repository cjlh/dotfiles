# TODO https://github.com/mathiasbynens/dotfiles/blob/main/.macos

# -- Global preferences

# Use cmd+ctrl to click-drag app windows
defaults write -g NSWindowShouldDragOnGesture -bool true

# -- Dock

# Semi-transparent icons for hidden apps
defaults write com.apple.dock showhidden -bool true

# -- Desktop and UI

# Disable Stage Manager
defaults write com.apple.WindowManager GloballyEnabled -bool false

# Disable "Click wallpaper to show desktop" (sets to "Only in Stage Manager")
defaults write com.apple.WindowManager EnableStandardClickToShowDesktop -bool false

# Increase timeout for screenshots to 20 seconds (default 5 seconds)
# To reset: `defaults delete com.apple.screencaptureui "thumbnailExpiration"`
defaults write com.apple.screencaptureui "thumbnailExpiration" -float 20 && killall SystemUIServer

# -- App-specific config

# Use cmd+shift+x for strikethrough in Stickies.app
defaults write com.apple.Stickies NSUserKeyEquivalents -dict-add "Strikethrough" '@$x'
