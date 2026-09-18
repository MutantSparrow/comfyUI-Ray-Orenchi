"""Assignment metrics, independent of how a palette was constructed."""
import numpy as np


def legacy_oklab(rgb):
    """Original node's CIE-shoulder OkLab variant, including its L rescale."""
    rgb = np.asarray(rgb, np.float32)
    linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
    m1 = np.array([[.4122214708,.5363325363,.0514459929],
                   [.2119034982,.6806995451,.1073969566],
                   [.0883024619,.2817188376,.6299787005]], np.float32)
    m2 = np.array([[.2104542553,.7936177850,-.0040720468],
                   [1.9779984951,-2.4285922050,.4505937099],
                   [.0259040371,.7827717662,-.8086757660]], np.float32)
    lms = np.maximum(linear @ m1.T, 0)
    delta = 6/29
    offset = 4/29
    transformed = np.where(lms > delta**3, np.cbrt(lms), lms/(3*delta**2)+offset)
    result = transformed @ m2.T
    result[...,0] = (result[...,0]-offset)/(1-offset)
    return result


def mapping_space(rgb, strategy, oklab, cie_lab):
    if strategy in ('oklab', 'color_families'):
        return oklab(rgb)
    if strategy == 'legacy_oklab':
        return legacy_oklab(rgb)
    if strategy == 'lab':
        return cie_lab(rgb).reshape(np.asarray(rgb).shape)/100
    if strategy == 'rgb':
        return np.asarray(rgb, np.float32)
    raise ValueError(f'Unknown palette mapping strategy: {strategy}')
