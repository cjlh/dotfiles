function fish_prompt
    set_color normal
    printf "["
    # set_color a8a8a8
    # set_color 89728A
    # set_color 55ff55
    set_color ecf28f
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
