load("@io_bazel_rules_go//go:def.bzl", "go_binary")
load("@bazel_skylib//rules:write_file.bzl", "write_file")

def pygo_go_binary(name, embed, bigslice = False, srcs = [], deps = [], visibility = None, **kwargs):
    if bigslice:
        go_binary(
            name = name + ".pygo_remote",
            embed = embed,
            srcs = srcs,
            deps = deps,
            visibility = ["//visibility:private"],
            x_defs = {
                "github.com/josh-newman/pygo/pygobigslice.isRemoteExe": "true",
            },
        )
        native.genrule(
            name = name + ".pygo_gen_remote_embed",
            srcs = [name + ".pygo_remote"],
            outs = [name + ".pygo_remote_embed.go"],
            cmd = """
                cp $< pygo_remote &&
                $(location @com_github_go_bindata_go_bindata//go-bindata) -pkg main -o $@ ./pygo_remote
            """,
            tools = ["@com_github_go_bindata_go_bindata//go-bindata"],
        )
        write_file(
            name = name + ".pygo_write_bigslice_embed_init",
            out = name + ".pygo_bigslice_embed_init.go",
            content = [_bigslice_embed_init],
        )
        srcs = srcs + [
            name + ".pygo_remote_embed.go",
            name + ".pygo_bigslice_embed_init.go",
        ]
        deps = deps + _bigslice_embed_init_deps

    go_binary(
        name = name,
        embed = embed,
        srcs = srcs,
        deps = deps,
        linkmode = "c-shared",
        visibility = visibility,
        **kwargs
    )

    # TODO: Add link test.

_gobcodec_label = "//python:gobcodec"

def pygo_py_library(name, go_binary, deps = [], **kwargs):
    _py_wrapper(name = name + ".py", go_binary = go_binary)
    if _gobcodec_label not in deps:
        deps = deps + [_gobcodec_label]
    native.py_library(
        name = name,
        srcs = [name + ".py"],
        deps = deps,
        data = [go_binary],  # Hacky workaround; see below.
        **kwargs
    )

    # In the original rules implementation with pyx_library depending on go_binary, .so loading
    # failed in some situations because libtensorflow could not be located.
    # Speculation: Because (for older rules_go versions) go_binary uses cc_import to expose the .so
    # to a cc_library, it may be losing the transitive .so dependencies, even though they're still
    # required (according to the ELF header, and at runtime).
    #
    # The current ctypes-based implementation resolves the cc_import symlink to a real path before
    # loading which seems to find the required libraries. This is a very hacky workaround that
    # depends on cc_import linking to an "original" .so where the relative paths work.
    #
    # If above is true, https://github.com/bazelbuild/rules_go/issues/2433, included in rules_go v0.26.0,
    # may fix the problem, because go_binary will return CcInfo directly, maybe keeping the transitive info.
    # TODO: Try `bazel test //experimental/users/joshnewman/python/pygo/pygotesting:classifier_test` after rules_go upgrade.
    #
    # Alternatively, rather than upgrade rules_go, we could try to "fix" the Cython .so output.
    # Right now, its RUNPATH (ELF header) points to a cc_import _solib entry whose own headers lead
    # to paths that don't work in the sandbox.
    # TODO: 1) Add the go_binary directly to `data`.
    # TODO: 2) Edit the pyx .so with patchelf, overwriting runpath to point to the go_binary in data.
    # Since the `py_library` arising from `pyx_library` should preserve its transitive data dependencies,
    # this may cause all the transitive .so's to be copied into the sandbox. Maybe.

_bigslice_embed_init = """
package main

import "github.com/josh-newman/pygo/pygobigslice"

func init() {
    pygobigslice.InternalSetRemoteExe(MustAsset("pygo_remote"))
}
"""

_bigslice_embed_init_deps = [
    "//pygobigslice:go_default_library",
]

def _py_wrapper_impl(ctx):
    pkg_depth = len(ctx.label.package.split("/"))
    so_relpath = ("../" * pkg_depth) + ctx.attr.go_binary.label.package
    out = ctx.actions.declare_file(ctx.attr.name)
    ctx.actions.expand_template(
        template = ctx.file._tmpl,
        output = out,
        substitutions = {
            "{SO_RELPATH}": so_relpath,
            "{SO_NAME_FRAGMENT}": ctx.attr.go_binary.label.name,
        },
    )
    return [DefaultInfo(files = depset([out]))]

_py_wrapper = rule(
    attrs = {
        "go_binary": attr.label(),
        "_tmpl": attr.label(
            allow_single_file = True,
            default = "//python/pygo:_pygo.tmpl.py",
        ),
    },
    implementation = _py_wrapper_impl,
)
