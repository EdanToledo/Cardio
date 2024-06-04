import torch as th
import numpy as np
import jax.numpy as jnp

# TODO: rename module so as to not be confused with typing


def to_np(arr: np.ndarray, dtype=np.float32):
    return arr.astype(dtype)


def to_jnp(arr: np.ndarray, dtype=jnp.float32):
    return jnp.asarray(arr, dtype=dtype)


def to_torch(arr: np.ndarray):
    return th.from_numpy(np.array(arr)).float()
