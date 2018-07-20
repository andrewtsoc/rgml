from itertools import combinations

import matplotlib.pyplot as plt
import numpy as np


class DIB:
    eps = 1e-12

    def __init__(self, pxx, beta=5, hiddens=100, iterations=10):
        self.beta = beta
        self.hiddens = hiddens
        self.iterations = iterations    # random initializations

        self.pxx = pxx  # joint distribution, 2D numpy array
        self.xsz = pxx.shape[0]

        # calculate marginals
        self.px = pxx.sum(axis=1)
        self.px = divide(self.px, self.px.sum())

        self.pxp = pxx.sum(axis=0)  # not assuming symmetry here
        self.pxp = divide(self.pxp, self.pxp.sum())

        self.beta = beta

        np.random.seed(0)

    def compress(self, epsilon=1e-4):
        self._initialize_clusters()
        self._update()

        prev_cost = 1e6

        idx = 0

        while abs(self.cost - prev_cost) > epsilon:
            print("Iteration %d: %.2f" % (idx, self.cost))
            prev_cost = self.cost
            self._step()
            self._cleanup()
            self._update()
            self._try_merge()
            self._cleanup()
            self._update()
            idx += 1

        self._cleanup()

        return self.cost

# core DIB helper functions #
    def _initialize_clusters(self):
        """
        randomly intialize clusters
        """
        # initialize clusters
        x = np.eye(self.hiddens)
        qt_x = x[:, np.random.randint(self.hiddens, size=self.xsz)]
        self.f = np.argmax(qt_x, axis=0)
        self.l = np.zeros((self.xsz, self.hiddens))

        self.cost = 0     # effectively infinity

    def _step(self):
        """
        updates cluster assignments by maximizing DIB objective
        """
        qt_x = self.l.T     # not correct, but should work for DIB scheme

        f = np.argmax(qt_x, axis=0)

        self.f = f

    def _try_merge(self):
        """
        try to merge clusters
        """
        f = self.f
        min_cost = self.cost

        for a, b in combinations(range(self.hiddens), 2):
            ftest = np.where(self.f == a, b, self.f)

            qt = np.zeros(self.hiddens)
            qy = np.zeros(self.hiddens)
            qy_t = np.zeros((self.hiddens, self.hiddens))

            for x in range(self.xsz):
                t = ftest[x]
                qt[t] += self.px[x]

            for xp in range(self.xsz):
                y = self.f[xp]
                qy[y] += self.pxp[xp]

            for x in range(self.xsz):
                for xp in range(self.xsz):
                    t = ftest[x]
                    y = ftest[xp]
                    qy_t[y, t] += divide(self.pxx[x, xp], qt[t])

            cost = self._calculate_cost(qy_t, qt, qy)

            if cost < min_cost:
                min_cost = cost
                f = ftest
                print("new low found %.2f by merging %d and %d" % (cost, a, b))

        self.f = f

    def _update(self):
        """
        recalculates q(t) and q(t|x) for current cluster assignments
        """
        self.qt = np.zeros(self.hiddens)
        self.qy = np.zeros(self.hiddens)
        self.qy_t = np.zeros((self.hiddens, self.hiddens))
        self.qy_x = np.zeros((self.hiddens, self.xsz))

        for x in range(self.xsz):
            t = self.f[x]
            self.qt[t] += self.px[x]

        for xp in range(self.xsz):
            y = self.f[xp]
            self.qy[y] += self.pxp[xp]

        for x in range(self.xsz):
            for xp in range(self.xsz):
                t = self.f[x]
                y = self.f[xp]
                self.qy_t[y, t] += divide(self.pxx[x, xp], self.qt[t])
                self.qy_x[y, x] += divide(self.pxx[x, xp], self.px[x])

        d = np.zeros((self.xsz, self.hiddens))
        for x in range(self.xsz):   # can this be simplified?
            for t in range(self.hiddens):
                for y in range(self.hiddens):
                    d[x, t] += self.qy_x[y, x] * (
                        np.log2(self.qy_x[y, x] + DIB.eps) -
                        np.log2(self.qy_t[y, t] + DIB.eps))

        self.l = np.log2(self.qt + DIB.eps) - self.beta * d

        self.cost = self._calculate_cost(self.qy_t, self.qt, self.qy)

    def _calculate_cost(self, qy_t, qt, qy):
        """
        calculate the DIB cost function of a proposed clustering
        """
        cost = 0
        for t in range(self.hiddens):
            cost -= qt[t] * np.log2(qt[t] + DIB.eps)

        for y in range(self.hiddens):
            for t in range(self.hiddens):
                cost -= self.beta * (qy_t[y, t] * qt[t]) * (
                    np.log2(qy_t[y, t] + DIB.eps) -
                    np.log2(qy[y] + DIB.eps))

        return cost

    def _cleanup(self):
        """
        cleanup and relabel unused clusters
        """
        # relabel clusters
        uniques = np.unique(self.f)
        unique_map = {v: i for i, v in enumerate(uniques)}
        self.f = np.vectorize(unique_map.get)(self.f)

        # remove unused bins
        self.qy_t = self.qy_t[:, np.sum(self.qy_t, axis=0) != 0]
        self.qt = self.qt[self.qt != 0]

        self.hiddens = uniques.size

# reporting and visualization #

    def report_clusters(self):
        """
        returns current cluster assignmetns
        """
        print("Found %d clusters with beta = %.2f" %
              (np.unique(self.f).size, self.beta))
        return self.f

    def visualize_clusters(self, vsz=3, debug=False):
        """
        displays clusters
        """
        qx_t = np.zeros((vsz*vsz, self.hiddens))
        finv = {x: set() for x in range(self.hiddens)}

        self.finv = finv

        for idx, element in enumerate(self.f):
            finv[element].add(idx)

        print({t: np.mean([bin(x).count('1') for x in finv[t]]) for t in finv})
        for t in finv:
            qx_t[:, t] = np.sum(
                np.array([self._bin2row(x, vsz*vsz) * self.px[x]
                          for x in finv[t]]), axis=0)

        # normalize cluster averages
        qx_t = qx_t / self.qt

        # reorder clusters by probability
        order = np.argsort(-self.qt)
        qx_t = qx_t[:, order]

        # reshape and plot
        if debug:
            clusters = np.zeros((vsz, vsz*self.hiddens))

            for t in finv:
                clusters[:, t*vsz:(t+1)*vsz] = \
                    qx_t[:, t].reshape(vsz, vsz)

            plt.matshow(clusters, cmap=plt.cm.gray)
            plt.show()

        return qx_t

    def mi_relevant(self):
        """
        returns mutual information between cluster assignments and environment
        I(T;Y)
        """
        mi = 0

        for y in range(self.hiddens):
            for t in range(self.hiddens):
                mi += self.qy_t[y, t] * self.qt[t] * (
                    np.log2(self.qy_t[y, t] + DIB.eps) -
                    np.log2(self.qy[y] + DIB.eps))

        return mi

    def mi_captured(self):
        """
        returns mutual information between cluster assignments and environment
        I(T;X)
        """
        mi = 0

        for x in range(self.xsz):
            for t in range(self.hiddens):
                mi += (self.f[x] == t) * self.px[x] * (
                    np.log2((self.f[x] == t) + DIB.eps) -
                    np.log2(self.qt[t] + DIB.eps))

        return mi

    def _bin2row(self, x, sz=9):
        """
        converts x to binary row (big endian)
        - this could probably be more efficient
        """
        return np.array([(x//2**k) % 2 == 1 for k in range(sz)])


# helpful functions #

def debugshow(thing):
    plt.matshow(thing, cmap=plt.cm.gray)
    plt.show()


def divide(a, b):
    """
    a / b, b==0 not used
    a better divide function
    """
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)
