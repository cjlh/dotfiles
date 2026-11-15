# Resume the least recently used stopped job. Allows repeated suspend/resume to cycle through jobs.
function __fish_resume_job
    set -l job (jobs | string match -r '^(\d+)\t.*\tstopped\t' -g)[-1]
    test -n "$job"; and fg %$job 2>/dev/null
    commandline -f repaint
end
