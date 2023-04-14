load("//bazel/python:exec.bzl", "py_exec")

py_exec(
    name = "exec",
    deps = [
        "//python/bio/fragments",
        "//python/classifier/classifierevalpy",
        "//python/gfile",
        "//python/tidydata",
    ],
)

py_library(
    name = "gobcodec",
    srcs = ["gobcodec.py"],
    visibility = ["//experimental/users/joshnewman:__subpackages__"],
)
