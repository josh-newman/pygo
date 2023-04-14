# load("//third_party/python:requirements.bzl", "requirement") # TODO: Fix.
load("//:rules.bzl", "pygo_py_library")

pygo_py_library(
    name = "pygobasic",
    go_binary = "//pygotesting/pygobasic",
    deps = [
        "//experimental/users/joshnewman/python:gobcodec",
        requirement("numpy"),
    ],
)

py_test(
    name = "basic_test",
    srcs = ["basic_test.py"],
    deps = [":pygobasic"],
)

pygo_py_library(
    name = "pygobigslice",
    go_binary = "//pygotesting/pygobigslice",
    tags = ["manual"],
)

py_test(
    name = "bigslice_internal_test",
    srcs = ["bigslice_internal_test.py"],
    deps = [":pygobigslice"],
)

py_test(
    name = "bigslice_ec2_test",
    srcs = ["bigslice_ec2_test.py"],
    deps = [":pygobigslice"],
    tags = ["manual"],
)
