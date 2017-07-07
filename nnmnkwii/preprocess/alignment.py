from __future__ import division, print_function, absolute_import

from nnmnkwii.utils import trim_zeros_frames
from nnmnkwii.baseline.gmm import MLParameterGeneration

from fastdtw import fastdtw

import numpy as np
from numpy.linalg import norm

import sklearn.mixture


class DTWAligner(object):
    def __init__(self, verbose=0, dist=lambda x, y: norm(x - y)):
        self.verbose = verbose
        self.dist = dist

    def transform(self, XY):
        X, Y = XY
        assert X.ndim == 3 and Y.ndim == 3

        X_aligned = np.zeros_like(X)
        Y_aligned = np.zeros_like(Y)
        for idx, (x, y) in enumerate(zip(X, Y)):
            x, y = trim_zeros_frames(x), trim_zeros_frames(y)
            dist, path = fastdtw(x, y, dist=self.dist)
            dist /= (len(x) + len(y))
            pathx = list(map(lambda l: l[0], path))
            pathy = list(map(lambda l: l[1], path))
            x, y = x[pathx], y[pathy]
            X_aligned[idx][:len(x)] = x
            Y_aligned[idx][:len(y)] = y
            if self.verbose > 0:
                print("{}, distance: {}".format(idx, dist))
        return X_aligned, Y_aligned


class IterativeDTWAligner(object):
    def __init__(self, n_iter=3, dist=lambda x, y: norm(x - y), verbose=0):
        self.n_iter = n_iter
        self.dist = dist
        self.verbose = verbose

    def transform(self, XY):
        X, Y = XY
        assert X.ndim == 3 and Y.ndim == 3

        Xc = X.copy()  # this will be updated iteratively
        X_aligned = np.zeros_like(X)
        Y_aligned = np.zeros_like(Y)
        refined_paths = np.empty(len(X), dtype=np.object)

        for idx in range(self.n_iter):
            for idx, (x, y) in enumerate(zip(Xc, Y)):
                x, y = trim_zeros_frames(x), trim_zeros_frames(y)
                dist, path = fastdtw(x, y, dist=self.dist)
                dist /= (len(x) + len(y))
                pathx = list(map(lambda l: l[0], path))
                pathy = list(map(lambda l: l[1], path))

                refined_paths[idx] = pathx
                x, y = x[pathx], y[pathy]
                X_aligned[idx][:len(x)] = x
                Y_aligned[idx][:len(y)] = y
                if self.verbose > 0:
                    print("{}, distance: {}".format(idx, dist))

            # Fit
            gmm = sklearn.mixture.GaussianMixture(
                n_components=32, covariance_type="full", max_iter=100)
            XY = np.concatenate((X_aligned, Y_aligned),
                                axis=-1).reshape(-1, X.shape[-1] * 2)
            gmm.fit(XY)
            paramgen = MLParameterGeneration(gmm, X.shape[-1])
            for idx in range(len(Xc)):
                x = trim_zeros_frames(Xc[idx])
                Xc[idx][:len(x)] = paramgen.transform(x)

        # Finally we can get aligned X
        for idx in range(len(X_aligned)):
            x = X[idx][refined_paths[idx]]
            X_aligned[idx][:len(x)] = x

        return X_aligned, Y_aligned