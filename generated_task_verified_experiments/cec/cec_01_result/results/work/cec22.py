"""ctypes wrapper around the official P-N-Suganthan CEC2022 C implementation.

Signature: void cec22_test_func(double *x, double *f, int nx, int mx, int func_num)
  - x : column-major array of shape (nx, mx): column j is individual j
  - f : output array of length mx (objective values)
  - nx: dimension, mx: number of points
The C code reads "input_data/*.txt" relative to the current working directory,
so callers must run from a directory that contains input_data/.
"""
import ctypes
import os
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = ctypes.CDLL(os.path.join(_HERE, "libcec22.so"))
_CEC = _LIB.cec22_test_func
_CEC.argtypes = [
    ctypes.POINTER(ctypes.c_double),  # x
    ctypes.POINTER(ctypes.c_double),  # f
    ctypes.c_int,                      # nx
    ctypes.c_int,                      # mx
    ctypes.c_int,                      # func_num
]
_CEC.restype = None

# Known global optima f* of the official CEC2022 suite (added as bias in the C code).
OPTIMA = {
    1: 300.0, 2: 400.0, 3: 600.0, 4: 800.0, 5: 900.0,
    6: 1800.0, 7: 2000.0, 8: 2200.0, 9: 2300.0, 10: 2400.0,
    11: 2600.0, 12: 2700.0,
}

# Bounds of the official CEC2022 bound-constrained suite.
LB, UB = -100.0, 100.0


def evaluate_batch(X, func_num):
    """Evaluate a (mx, nx) array of row-vectors. Returns (mx,) objective values."""
    X = np.ascontiguousarray(X, dtype=np.float64)
    mx, nx = X.shape
    xcol = np.asfortranarray(X.T)           # (nx, mx) column-major
    f = np.zeros(mx, dtype=np.float64)
    _CEC(xcol.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
         f.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),
         nx, mx, func_num)
    return f


class CEC2022Problem:
    """Stateful wrapper: caches a func_num, exposes a batch objective."""

    def __init__(self, func_num, dim=20):
        assert func_num in OPTIMA
        self.func_num = func_num
        self.dim = dim
        self.lb = LB
        self.ub = UB
        self.optimum = OPTIMA[func_num]
        # Warm the C globals once (loads M / shift data for this func_num, dim).
        evaluate_batch(np.zeros((1, dim)), func_num)

    def __call__(self, X):
        return evaluate_batch(X, self.func_num)
