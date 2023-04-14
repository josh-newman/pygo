import dataclasses
import math
import unittest

import numpy as np

from python import gobcodec
from python.pygo.pygotesting import pygobasic


@dataclasses.dataclass
class _Test1:
    A: int
    B: int
    C: str


# _test_objs corresponds to the test list in pygodemo.py.
_test_objs = (
    (0,),
    (3,),
    (127,),
    (128,),
    (220,),
    (32983,),
    (-3,),
    (-127,),
    (-128,),
    (-220,),
    (-32983,),
    (True,),
    (False,),
    (True,),
    (0.0,),
    (1.0,),
    (-1.0,),
    (-1.5,),
    (1.5,),
    (3.14159265358979323846264338327950288419716939937510582097494459,),
    (math.inf,),
    (-math.inf,),
    ("",),
    ("hello",),
    ("@&*X(",),
    ("a\t \nb",),
    ([7, 8, 9],),
    (["A", "B"],),
    ({"a": 1, "b": 2},),
    (["a"], 1),
    ({"a": 1, "b": 2}, 3.0),
)
_test_objs_send_only = (gobcodec.GoInterfaceValue("string", "hello"),)
_test_objs_gosend_numpy = (
    np.array([1, 2, 3]),
    np.array([4., 5.6, 7.8]),
)
# Still corresponds to the Go test list, but we compare these differently.
_test_objs_classes = (
    _Test1(1, None, "2"),
    gobcodec.GoInterfaceValue("pygo_test1", _Test1(3, 7, None)),
)


class TestPyGo(unittest.TestCase):
    def test_gorecv(self):
        for test_idx, args in enumerate(_test_objs):
            pygobasic.call(f"test_gorecv_{test_idx}", *args)

    def test_gosend(self):
        test_idx = 0
        for rets in _test_objs:
            gots = pygobasic.call(f"test_gosend_{test_idx}")
            if len(rets) == 1:
                gots = (gots,)
            self.assertEqual(gots, rets)
            test_idx += 1
        for obj in _test_objs_send_only:
            got = pygobasic.call(f"test_gosend_{test_idx}")
            self.assertEqual(got, obj)
            test_idx += 1
        for obj in _test_objs_gosend_numpy:
            self.assertTrue(np.array_equal(pygobasic.call(f"test_gosend_{test_idx}"), obj))
            test_idx += 1
        for obj in _test_objs_classes:
            self.assertEqual(
                dataclasses.asdict(pygobasic.call(f"test_gosend_{test_idx}")),
                dataclasses.asdict(obj),
            )
            test_idx += 1

    def test_float(self):
        pygobasic.call("test_gorecv_nan", math.nan)

    def test(self):
        self.assertEqual(pygobasic.call("strings.Contains", "hello world", "hello"), True)


if __name__ == "__main__":
    unittest.main()
