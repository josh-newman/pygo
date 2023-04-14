def py_exec(name, deps):
    """
    py_exec defines an executable that runs in a Python environment with the specified dependencies.

    Example usage:
        $ bazel run //experimental/my_project:exec -- ipython3
    This runs ipython3 with access to all the libraries named in the deps of
    //experimental/my_project:exec.

    Alternatively, pass `--python` instead of an executable name to just run Python (with all
    the right deps).
        $ bazel run //experimental/my_project:exec -- --python -m my_module
    """

    native.py_binary(
        name = name,
        srcs = ["//bazel/python:exec.py"],
        main = "exec.py",
        tags = ["manual"],
        deps = deps,
    )
