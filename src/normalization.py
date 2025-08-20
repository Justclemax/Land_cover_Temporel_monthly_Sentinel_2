import  numpy as np

def normalize(array):
    """Normalize a numpy array to the range 0.0 - 1.0"""
    array_min, array_max = np.nanmin(array), np.nanmax(array)

    if array_max == array_min:
        return np.zeros_like(array)

    return (array - array_min) / (array_max - array_min)