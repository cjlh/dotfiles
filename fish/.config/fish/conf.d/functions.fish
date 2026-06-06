# Utility functions

function cd -w cd -d "automatically activate and deactivate virtualenvs"
    builtin cd $argv
    if test -e venv/bin/activate.fish
        source venv/bin/activate.fish
    else if test -e .venv/bin/activate.fish
        source .venv/bin/activate.fish
    else if set -q VIRTUAL_ENV
        # returns 0 if subpath of dir containing current virtualenv, 1 otherwise
        string match -q "$(string lower (path normalize "$VIRTUAL_ENV/.."))*" "$(string lower (pwd))"
        if test $status -eq 1
            deactivate
        end
    end
end

function mkcd
    mkdir $argv; and builtin cd $argv
end

function j -d "use just command runner and rename terminal title"
    # https://github.com/fish-shell/fish-shell/issues/8798
    if test (count $argv) -eq 1
        echo -n -e "\e]0;$argv (just)\a"
    end
    just $argv
end
