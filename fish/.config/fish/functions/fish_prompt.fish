# Left-side prompt
function fish_prompt
    set_color normal
    printf "["
    # set_color -o a8a8a8
    # set_color -o 89728A
    # set_color -o 55ff55
    set_color -o ecf28f
    printf "$USER"
    set_color normal
    set directory
    # printf ":"
    #set_color -i
    printf " in "
    set_color -i
    if [ $PWD = $HOME ]
        printf "~"
    else
        echo -n (basename $PWD)
    end
    set_color normal
    printf "] "
end

function fish_right_prompt
    set -f LENGTH_LIMIT 20
    set_color -o 95989d
    git rev-parse --abbrev-ref HEAD &> /dev/null
    if test $status -eq 0
        set -f branch_name (git rev-parse --abbrev-ref HEAD)
        set -f length (string length $branch_name)
        if test $length -lt (math "$LENGTH_LIMIT + 1")
            echo "$branch_name "
        else
            set -f left (string shorten -m(math "ceil($LENGTH_LIMIT / 2) + 1") $branch_name)
            set -f right (string sub -s -(math "floor($LENGTH_LIMIT / 2) - 1") $branch_name)
            echo "$left$right "
        end
    end
    date "+%H:%M"
end

# Right-side prompt
# function fish_right_prompt
#   date "+%H:%M "
# end

