# pygo

Pygo is an experimental, incomplete prototype for writing Python native modules in Go.
Go code registers specific methods to be callable. Python code imports modules (built with
bazel's help) and calls functions.

A partial implementation of Go's encoding/gob format, in python/gobcodec.py, serializes function
call arguments and returns.

It's all very slow and wasn't used for anything serious yet. This repository was extracted from
some experimental, unused, internal code, and would need some work to build:
* Use bigslice's current configuration method, base/config.
* Run gazelle to generate bazel BUILD files for Go code.
* Probably fix a bunch of things after that.
