# Utility functions

function mkcd --description "Create a new directory and enter it"
    if test (count $argv) -ne 1
        echo "Usage: mkcd DIRECTORY" >&2
        return 2
    end

    set -l target $argv[1]

    if test -z "$target"
        echo "mkcd: directory name cannot be empty" >&2
        return 2
    end

    # A file (or a broken symlink) already at this path makes mkdir -p fail
    if test -e "$target" -o -L "$target"; and not test -d "$target"
        echo "mkcd: '$target' exists and is not a directory" >&2
        return 1
    end

    mkdir -p -- "$target"; or return 1

    # Anchor relative paths so CDPATH can't redirect us and names like "-" aren't treated as options
    if not string match -q -- '/*' "$target"
        set target "./$target"
    end

    cd -- "$target"
end

function cvdir --description "Replace an empty directory with a file of the same name (e.g. if accidentally used mkdir instead of touch)"
    if test (count $argv) -ne 1
        echo "Usage: cvdir DIRECTORY" >&2
        return 2
    end

    # Strip trailing slashes so tab-completed "foo/" works (leaves "/" alone)
    set -l target (string replace -r '(?<=.)/+$' '' -- $argv[1])

    if test -L "$target"
        echo "cvdir: '$target' is a symlink, not a directory" >&2
        return 1
    else if not test -e "$target"
        echo "cvdir: '$target' does not exist" >&2
        return 1
    else if not test -d "$target"
        echo "cvdir: '$target' is not a directory" >&2
        return 1
    end

    # Include dotfiles; fish's .* never matches . or ..
    set -l contents $target/* $target/.*
    if set -q contents[1]
        echo "cvdir: '$target' is not empty ("(count $contents)" entries)" >&2
        return 1
    end

    rmdir -- "$target"; or return 1
    touch -- "$target"; or begin
        echo "cvdir: removed '$target' but failed to create the file" >&2
        return 1
    end
end

function du-sort --description "List all the children of the current directory, ordered by size"
    du -hs $argv[1]/* | sort -h
end

function git-stash-store --description "Save a snapshot of the working tree into the stash, without modifying the working tree"
    # First argument (optional) is the stash message
    if test -n "$argv[1]"
        git stash store -m "$argv[1]" (git stash create "$argv[1]")
    else
        set HASH (git stash create)
        set MESSAGE (git log --no-walk --pretty="tformat:%-s" "$HASH")
        git stash store -m "$MESSAGE" "$HASH"
    end
end

function gdu --description "Diff all untracked files in one git diff"
    set -l files (git ls-files --others --exclude-standard)
    test (count $files) -eq 0; and return
    git add --intent-to-add -- $files
    git diff -- $files
    git reset --quiet -- $files
end

function docker-stop-all --description "Stop all running Docker containers"
    set -l containers (docker ps -q)

    if test (count $containers) -gt 0
        docker stop $containers
    else
        echo "No running containers"
    end
end

function docker-nuke --description "Delete all Docker build artefacts, images, containers, and volumes"
    # If disk too full for Docker to start, delete virtual disk, i.e. at:
    # ~/Library/Containers/com.docker.docker/Data/vms/0/data/Docker.raw
    docker buildx prune -af
    docker builder prune -af
    docker system prune -af --volumes
end

function j --description "Use just command runner and rename terminal title"
    # https://github.com/fish-shell/fish-shell/issues/8798
    if test (count $argv) -eq 1
        echo -n -e "\e]0;$argv (just)\a"
    end
    just $argv
end

function __du_repos_heading
    isatty stdout; and set_color --bold
    echo $argv
    isatty stdout; and set_color normal
end

function __du_repos_human --argument-names kb
    set -l size $kb
    for unit in K M G T
        if test (math --scale 0 $size) -lt 1024; or test $unit = T
            printf "%.1f%s" $size $unit
            return
        end
        set size (math $size / 1024)
    end
end

function du-repos --description "Disk usage of every repo/worktree root under a path, sorted by size"
    if test (count $argv) -ne 1
        echo "Usage: du-repos <path>" >&2
        return 2
    end
    if not test -d "$argv[1]"
        echo "du-repos: Not a directory: $argv[1]" >&2
        return 2
    end
    set -l base (path resolve "$argv[1]")

    set -l live
    isatty stdout; and set live 1
    if set -q live[1]
        # Use alternative screen for live progress so it can be rewriten without messing up buffer
        printf "\e[?1049h"
        # If interrupted, leave the alternate screen before the next prompt is drawn
        function __du_repos_restore --on-event fish_prompt
            printf "\e[?1049l"
            functions -e __du_repos_restore
        end
    end

    set -l results
    set -l display
    # `-prune` stops descent at git repo (.git dir present) or worktree (.git file present)
    find $base -type d -exec test -e "{}/.git" ";" -print0 -prune 2>/dev/null \
        | xargs -0 -n1 -P8 du -sk 2>/dev/null \
        | while read -l -d \t kb root
            set -a results $kb\t$root
            set -a display (__du_repos_human $kb)\t(string replace -- "$base/" "" $root)
            set -q live[1]; or continue
            # $LINES/$COLUMNS aren't refreshed while a function runs, so ask the terminal directly
            set -l rows_cols (string split " " (stty size </dev/tty))
            set -l n (count $display)
            set -l start (math "max(1, $n - $rows_cols[1] + 3)")
            printf "\e[?2026h\e[H\e[J"
            printf "%d roots sized…\n" $n
            string shorten -m (math $rows_cols[2] - 8) -- $display[$start..-1]
            printf "\e[?2026l"
        end

    if set -q live[1]
        printf "\e[?1049l"
        functions -e __du_repos_restore
    end

    __du_repos_heading "All repos"
    set -l total 0
    set -l grouped
    for result in (printf "%s\n" $results | sort -n)
        set -l kb_root (string split -m1 \t -- $result)
        set total (math $total + $kb_root[1])
        printf "%s\t%s\n" (__du_repos_human $kb_root[1]) (string replace -- "$base/" "" $kb_root[2])
        # Worktrees share their main checkout's git dir, so group each root under that checkout
        set -l main $kb_root[2]
        set -l common_dir (git -C $main rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
        and set main (path dirname $common_dir)
        set -a grouped $kb_root[1]\t(string replace -- "$base/" "" $main)
    end

    echo
    __du_repos_heading "Per repo"
    printf "%s\n" $grouped \
        | awk -F"\t" '{ kb[$2] += $1; n[$2]++ } END { for (repo in kb) print kb[repo] "\t" n[repo] "\t" repo }' \
        | sort -n \
        | while read -l -d \t kb n repo
            set -l label $repo
            test $n -gt 1; and set label "$repo ($n worktrees)"
            printf "%s\t%s\n" (__du_repos_human $kb) $label
        end

    echo
    __du_repos_heading Total
    echo (__du_repos_human $total)
end

function du-work --description "Disk usage of every repo/worktree root under ~/Work, sorted by size"
    du-repos ~/Work
end

function du-projects --description "Disk usage of every repo/worktree root under ~/Projects, sorted by size"
    du-repos ~/Projects
end
