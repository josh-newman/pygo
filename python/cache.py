import inspect
import os
import pickle
import re
import tempfile
import typing
import weakref


class Cache:
    def __init__(self, disk_path: typing.Optional[str] = None):
        self.cache_dir = disk_path
        self.mem = {}
        self.weakmem = {}

    def path(self, *args, extra_key=None, **kwargs):
        """
        Path returns a file path within the cache directory. Use when `fn`'s management of
        computation is not desired.
        """
        filename = os.path.join(
            self.cache_dir,
            inspect.stack()[1].function,
            _format_filename(*args, extra_key=extra_key, **kwargs),
        )
        cache_dir = os.path.dirname(filename)
        os.makedirs(cache_dir, exist_ok=True)
        return filename

    def fn(self, result, *args, mem=False, weakmem=False, extra_key=None, **kwargs):
        """
        Cache the value returned by result using a cache key generated from function name
        and args.
        """
        filename = os.path.join(
            self.cache_dir,
            inspect.stack()[1].function,
            _format_filename(*args, extra_key=extra_key, **kwargs),
        )

        def from_disk():
            if not os.path.exists(filename):
                r = result()
                cache_dir = os.path.dirname(filename)
                os.makedirs(cache_dir, exist_ok=True)
                tmpf, tmpname = tempfile.mkstemp(dir=cache_dir)
                os.close(tmpf)
                try:
                    with open(tmpname, "wb") as f:
                        pickle.dump(r, f)
                except:
                    os.remove(tmpname)
                    raise
                os.rename(tmpname, filename)
            with open(filename, "rb") as f:
                return pickle.load(f)

        assert not (mem and weakmem)
        if mem:
            if filename not in self.mem:
                self.mem[filename] = from_disk()
            return self.mem[filename]
        if weakmem:
            if filename in self.weakmem:
                obj = self.weakmem[filename]()
                if obj is not None:
                    return obj
            obj = from_disk()
            self.weakmem[filename] = weakref.ref(obj)
            return obj
        return from_disk()


def from_relpath(relpath: str, tmpdir="/mnt/data/tmp"):
    return Cache(
        os.path.join(
            tmpdir,
            "py.nb.fncache",
            relpath,
            os.path.basename(inspect.stack()[1].filename),
        )
    )


def _format_filename(*args, extra_key=None, **kwargs):
    return (
        "result_"
        + ((extra_key + "_") if extra_key else "")
        + ",".join(re.sub(r"[^a-zA-Z0-9._-]", "_", str(arg)) for arg in args)
        + ",".join(
            k + "=" + re.sub(r"[^a-zA-Z0-9._-]", "_", str(arg))
            for k, arg in kwargs.items()
        )
    )

