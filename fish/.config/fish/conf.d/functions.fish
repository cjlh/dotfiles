# Utility functions

function mkcd
    mkdir -p $argv[1]
    if test -d "$argv[1]"
        builtin cd $argv[1]
    end
end

function git-stash-store
    # Save snapshot of working tree into the stash without modifying working tree
    # First argument (optional) is the stash message
    if test -n "$argv[1]"
        git stash store -m "$argv[1]" (git stash create "$argv[1]")
    else
        set HASH (git stash create)
        set MESSAGE (git log --no-walk --pretty="tformat:%-s" "$HASH")
        git stash store -m "$MESSAGE" "$HASH"
    end
end

function docker-stop-all
    set -l containers (docker ps -q)

    if test (count $containers) -gt 0
        docker stop $containers
    else
        echo "No running containers"
    end
end

function docker-nuke
    docker buildx prune -af
    docker builder prune -af
    docker system prune -af --volumes
end

function j -d "use just command runner and rename terminal title"
    # https://github.com/fish-shell/fish-shell/issues/8798
    if test (count $argv) -eq 1
        echo -n -e "\e]0;$argv (just)\a"
    end
    just $argv
end
