# virtualenv activation module
# Activate with `overlay use activate.nu`
# Deactivate with `deactivate`, as usual
#
# To customize the overlay name, you can call `overlay use activate.nu as foo`,
# but then simply `deactivate` won't work because it is just an alias to hide
# the "activate" overlay. You'd need to call `overlay hide foo` manually.

export-env {
    def is-string [x] {
        ($x | describe) == 'string'
    }

    def has-env [name: string] {
        $name in (env).name
    }

    # Emulates a `test -z`, but btter as it handles e.g 'false'
    def is-env-true [name: string] {
      if (has-env $name) {
        # Try to parse 'true', '0', '1', and fail if not convertible
        let parsed = do -i { $env | get $name | into bool }
        if ($parsed | describe) == 'bool' {
          $parsed
        } else {
          not ($env | get $name | is-empty)
        }
      } else {
        false
      }
    }

    let is_windows = ($nu.os-info.name | str downcase) == 'windows'
    let virtual_env = '__VIRTUAL_ENV__'
    let bin = '__BIN_NAME__'
    let path_sep = (char esep)
    let path_name = if $is_windows {
        if (has-env 'Path') {
            'Path'
        } else {
            'PATH'
        }
    } else {
        'PATH'
    }

    let old_path = (
        if $is_windows {
            if (has-env 'Path') {
                $env.Path
            } else {
                $env.PATH
            }
        } else {
            $env.PATH
        } | if (is-string $in) {
            # if Path/PATH is a string, make it a list
            $in | split row $path_sep | path expand
        } else {
            $in
        }
    )

    let venv_path = ([$virtual_env $bin] | path join)
    let new_path = ($old_path | prepend $venv_path | str collect $path_sep)

    let new_env = {
        $path_name  : $new_path
        VIRTUAL_ENV : $virtual_env
    }

    let new_env = if (is-env-true 'VIRTUAL_ENV_DISABLE_PROMPT') {
      $new_env
    } else {
      # Creating the new prompt for the session
      let virtual_prompt = if ('__VIRTUAL_PROMPT__' == '') {
          $'(char lparen)($virtual_env | path basename)(char rparen) '
      } else {
          '(__VIRTUAL_PROMPT__) '
      }

      # Back up the old prompt builder
      let old_prompt_command = if (has-env 'VIRTUAL_ENV') and (has-env '_OLD_PROMPT_COMMAND') {
          $env._OLD_PROMPT_COMMAND
      } else {
          if (has-env 'PROMPT_COMMAND') {
              $env.PROMPT_COMMAND
          } else {
              ''
          }
      }

      # If there is no default prompt, then only the env is printed in the prompt
      let new_prompt = if (has-env 'PROMPT_COMMAND') {
          if ($old_prompt_command | describe) == 'block' {
              { $'($virtual_prompt)(do $old_prompt_command)' }
          } else {
              { $'($virtual_prompt)($old_prompt_command)' }
          }
      } else {
          { $'($virtual_prompt)' }
      }

      $new_env | merge {
        _OLD_VIRTUAL_PATH   : ($old_path | str collect $path_sep)
        _OLD_PROMPT_COMMAND : $old_prompt_command
        PROMPT_COMMAND      : $new_prompt
        VIRTUAL_PROMPT      : $virtual_prompt
      }
    }

    # Environment variables that will be loaded as the virtual env
    load-env $new_env
}

export alias pydoc = python -m pydoc
export alias deactivate = overlay hide activate
