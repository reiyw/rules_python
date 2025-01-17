"Set defaults for the pip-compile command to run it under Bazel"

import os
import sys
from shutil import copyfile

from piptools.scripts.compile import cli

if len(sys.argv) < 4:
    print(
        "Expected at least two arguments: requirements_in requirements_out",
        file=sys.stderr,
    )
    sys.exit(1)

requirements_in = os.path.relpath(sys.argv.pop(1))
requirements_txt = sys.argv.pop(1)
update_target_name = sys.argv.pop(1)

# Before loading click, set the locale for its parser.
# If it leaks through to the system setting, it may fail:
# RuntimeError: Click will abort further execution because Python 3 was configured to use ASCII
# as encoding for the environment. Consult https://click.palletsprojects.com/python3/ for
# mitigation steps.
os.environ["LC_ALL"] = "C.UTF-8"
os.environ["LANG"] = "C.UTF-8"

UPDATE = True
# Detect if we are running under `bazel test`
if "TEST_TMPDIR" in os.environ:
    UPDATE = False
    # pip-compile wants the cache files to be writeable, but if we point
    # to the real user cache, Bazel sandboxing makes the file read-only
    # and we fail.
    # In theory this makes the test more hermetic as well.
    sys.argv.append("--cache-dir")
    sys.argv.append(os.environ["TEST_TMPDIR"])
    # Make a copy for pip-compile to read and mutate
    requirements_out = os.path.join(
        os.environ["TEST_TMPDIR"], os.path.basename(requirements_txt) + ".out"
    )
    copyfile(requirements_txt, requirements_out)

elif "BUILD_WORKING_DIRECTORY" in os.environ:
    os.chdir(os.environ['BUILD_WORKING_DIRECTORY'])
else:
    print(
        "Expected to find BUILD_WORKING_DIRECTORY in environment",
        file=sys.stderr,
    )
    sys.exit(1)

update_target_pkg = "/".join(requirements_in.split('/')[:-1])
# $(rootpath) in the workspace root gives ./requirements.in
if update_target_pkg == ".":
    update_target_pkg = ""
update_command = os.getenv("CUSTOM_COMPILE_COMMAND") or "bazel run //%s:%s" % (update_target_pkg, update_target_name)

os.environ["CUSTOM_COMPILE_COMMAND"] = update_command

sys.argv.append("--generate-hashes")
sys.argv.append("--output-file")
sys.argv.append(requirements_txt if UPDATE else requirements_out)
sys.argv.append(requirements_in)

if UPDATE:
    print("Updating " + requirements_txt)
    cli()
else:
    # cli will exit(0) on success
    try:
        print("Checking " + requirements_txt)
        cli()
        print("cli() should exit", file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        golden = open(requirements_txt).readlines()
        out = open(requirements_out).readlines()
        if golden != out:
            import difflib

            print(''.join(difflib.unified_diff(golden, out)), file=sys.stderr)
            print(
                "Lock file out of date. Run '"
                + update_command
                + "' to update.",
                file=sys.stderr,
            )
            sys.exit(1)
