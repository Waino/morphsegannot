from __future__ import unicode_literals

import Levenshtein
import numpy as np

def representative_sampling(words, k):
    dist = distances(words)
    medoids, _ = best_of(dist, k)
    for m in medoids:
        yield words[m]


def distances(words):
    # symmetry is wasted
    dist = Levenshtein.compare_lists(words, words, 0.0, 0)
    return dist


def k_medoids(dist, k, tmax=100):
    m, n = dist.shape
    # randomly initialize an array of k medoid indices
    medoids = np.arange(n)
    np.random.shuffle(medoids)
    medoids = medoids[:k]
    medoids_old = np.copy(medoids)
    clusters = {}
    for t in xrange(tmax):
        # determine clusters, i.e. arrays of data indices
        J = np.argmin(dist[:, medoids], axis=1)
        for current in range(k):
            clusters[current] = np.where(J == current)[0]
        # update cluster medoids
        for current in range(k):
            J = np.mean(
                dist[np.ix_(clusters[current], clusters[current])],
                axis=1)
            j = np.argmin(J)
            medoids[current] = clusters[current][j]
        np.sort(medoids)
        # check for convergence
        if np.array_equal(medoids_old, medoids):
            break
        medoids_old = np.copy(medoids)
    else:
        # final update of cluster memberships
        J = np.argmin(dist[:, medoids], axis=1)
        for current in range(k):
            clusters[current] = np.where(J == current)[0]
    wcvars = np.zeros_like(medoids)
    for current in range(k):
        wcvars[current] = np.sum(dist[clusters[current], medoids[current]] ** 2)
    return medoids, clusters, wcvars


def best_of(dist, k, tmax=100, repeats=10):
    best = None
    cost = None
    for _ in xrange(repeats):
        medoids, clusters, wcvars = k_medoids(dist, k, tmax)
        cost_new = np.sum(wcvars)
        if cost is None or cost_new < cost:
            best = (medoids, clusters)
            cost = cost_new
    return best
