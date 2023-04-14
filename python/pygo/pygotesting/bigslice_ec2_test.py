from python.pygo.pygotesting import pygobigslice


def _main():
    pygobigslice.call("pygo_bigslice_use_ec2", "instance=m5.large,ondemand=true")
    pygobigslice.call(
        "pygo_bigslice_add_flags",
        [
            "-system=ec2pygo:instance=m5.large,ondemand=true",
            "-parallelism=1",
        ],
    )
    results = pygobigslice.call(
        "pygo_bigslice_demo_stat",
        ["s3://commoncrawl/index.html"],
    )
    print(results)


if __name__ == "__main__":
    _main()
