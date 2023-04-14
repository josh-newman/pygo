#!/usr/bin/env python3

import os
import sys


_WORKING_DIR_ENV_VAR = "BUILD_WORKING_DIRECTORY"


def _main():
    if len(sys.argv) < 2:
        print("exec requires a command", file=sys.stderr)
        sys.exit(2)

    cmd = sys.argv[1]
    if cmd == "--python":
        cmd = sys.executable

    if _WORKING_DIR_ENV_VAR in os.environ:
        os.chdir(os.environ[_WORKING_DIR_ENV_VAR])
    else:
        print(
            f"INFO: Running `{cmd}` in Bazel execution directory: {os.getcwd()}",
            file=sys.stderr,
        )

    os.execvp(cmd, [cmd] + sys.argv[2:])


if __name__ == "__main__":
    _main()
