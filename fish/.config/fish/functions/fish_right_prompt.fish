function fish_right_prompt
    set_color --bold 95989d

    set -l length_limit 20
    set -l branch_name (command git rev-parse --abbrev-ref HEAD 2>/dev/null)

    if test $status -eq 0
        if test (string length -- "$branch_name") -gt $length_limit
            set -l left (string shorten --max (math "ceil($length_limit / 2) + 1") -- "$branch_name")
            set -l right (string sub --start -(math "floor($length_limit / 2) - 1") -- "$branch_name")
            set branch_name "$left$right"
        end
        printf '%s ' "$branch_name"
    end

    printf '%s' (date '+%H:%M')
end
