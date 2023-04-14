import array
import ctypes
import os
import sys

from python import gobcodec


class _PygoTuple(ctypes.Structure):
    _fields_ = (
        ("num", ctypes.c_int),
        ("data_size", ctypes.c_size_t),
        ("data", ctypes.POINTER(ctypes.c_ubyte)),
    )


class _PygoRequest(ctypes.Structure):
    _fields_ = (
        ("func_name", ctypes.c_char_p),
        ("ins", _PygoTuple),
        ("outs", _PygoTuple),
    )


def _find() -> str:
    so_dir = os.path.join(os.path.dirname(__file__), "{SO_RELPATH}")
    for parent, unused_dirs, files in os.walk(so_dir):
        for f in files:
            root, ext = os.path.splitext(f)
            if "{SO_NAME_FRAGMENT}" in root and ext == ".so":
                p = os.path.join(parent, f)
                # Resolve symlinks as a workaround for the (apparent?) bazel cc_import problem
                # described in pygo/rules.bzl. TODO: Remove realpath() call.
                p = os.path.realpath(p)
                return p
    raise IOError("library not found")


_lib = ctypes.CDLL(_find())
_lib.grail_pygo_call.argtypes = [ctypes.POINTER(_PygoRequest)]
_lib.grail_pygo_call.restype = ctypes.c_char_p
_lib.grail_pygo_free.argtypes = [ctypes.POINTER(_PygoRequest)]


class CallError(Exception):
    pass


def call(name: str, *args, known_types=tuple()):
    req = _PygoRequest()
    req.func_name = name.encode("utf-8")

    req.ins.num = len(args)
    enc = gobcodec.Encoder()
    encoded_args = [enc.encode(a) for a in args]
    req.ins.data_size = int(sum(len(ea) for ea in encoded_args))
    ins_data = (ctypes.c_ubyte * req.ins.data_size)(
        *(b for ea in encoded_args for b in ea)
    )
    req.ins.data = ctypes.cast(ins_data, ctypes.POINTER(ctypes.c_ubyte))

    err = _lib.grail_pygo_call(ctypes.byref(req))
    if err:
        _lib.grail_pygo_free(ctypes.byref(req))
        # TODO: Free `err`.
        raise CallError(err.decode("utf-8"))

    dec = gobcodec.Decoder(known_types=known_types)
    # TODO: Is this making extra copies?
    outs_data = bytes(
        ctypes.cast(req.outs.data, ctypes.POINTER(ctypes.c_ubyte))[: req.outs.data_size]
    )
    outs_num = req.outs.num
    _lib.grail_pygo_free(ctypes.byref(req))
    outs = dec.decode_all(outs_data)
    assert len(outs) == outs_num
    return outs[0] if len(outs) == 1 else outs
