if status is-interactive
      # Perform a final prompt render immediately before command execution
      set -g fish_transient_prompt 1

      function __prompt_clock_repaint --on-signal SIGUSR1
          commandline --function repaint
      end

      # Avoid starting another timer if the configuration is sourced again
      if not set -q __prompt_clock_pid
          or not kill -0 $__prompt_clock_pid 2>/dev/null

          fish --no-config -c '
              while kill -0 $argv[1] 2>/dev/null
                  # Wake at the beginning of the next minute.
                  set -l delay (math "60 - "(date +%S))
                  sleep $delay

                  kill -s USR1 $argv[1] 2>/dev/null
                  or break
              end
          ' $fish_pid &

          set -g __prompt_clock_pid $last_pid
          disown $__prompt_clock_pid
      end
  end
