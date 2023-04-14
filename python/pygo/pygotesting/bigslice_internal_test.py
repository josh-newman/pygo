from python.pygo.pygotesting import pygobigslice


def _main():
    pygobigslice.call(
        "pygo_bigslice_demo_stat",
        ["s3://commoncrawl/index.html"],
    )


if __name__ == "__main__":
    _main()
