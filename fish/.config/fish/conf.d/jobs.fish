# Job handling and messaging

# Silence "Job N, '...' has stopped" notices when suspending applications

functions -q fish_job_summary; and functions -c fish_job_summary __fish_default_job_summary

function fish_job_summary
    test "$argv[4]" = STOPPED; and return
    __fish_default_job_summary $argv
end
