#!/usr/bin/env python

"""
manca: microbial association network clustering algorithm
manca takes a networkx (weighted) microbial network as input and
uses a diffusion-based process to iterate over the network.
After the sparsity values converge, the resulting cluster set
should have a minimum sparsity value.
"""

__author__ = 'Lisa Rottjers'
__email__ = 'lisa.rottjers@kuleuven.be'
__status__ = 'Development'
__license__ = 'Apache 2.0'

import networkx as nx
from random import choice
import numpy as np
import sys
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import argparse

def set_manca():
    """This parser gets input settings for running the manca clustering algorithm.
    Apart from the parameters specified by cluster_graph,
    it requires an input format that can be read by networkx."""
    parser = argparse.ArgumentParser(
        description='Run the microbial association network clustering algorithm.')
    parser.add_argument('-i', '--input_graph',
                        dest='graph',
                        help='Input network file.',
                        default=None, required=True)
    parser.add_argument('-o', '--output_graph',
                        dest='fp',
                        help='Output network file.',
                        default=None, required=True)
    parser.add_argument('-f', '--file_type',
                        dest='f',
                        help='Format of network file.',
                        choices=['gml', 'edgelist',
                                 'graphml', 'adj'],
                        default='graphml')
    parser.add_argument('-limit', '--convergence_limit',
                        dest='limit',
                        required=False,
                        help='The convergence limit '
                             'specifies how long the algorithm will repeat after '
                             'reaching equal sparsity values. ',
                        default=100)
    parser.add_argument('-df', '--diffusion_range',
                        dest='df',
                        required=False,
                        help='Diffusion is considered over a range of k neighbours. ',
                        default=3)
    parser.add_argument('-mc', '--max_clusters',
                        dest='mc',
                        required=False,
                        help='Number of clusters to consider in K-means clustering. ',
                        default=4)
    parser.add_argument('-iter', '--iterations',
                        dest='iter',
                        required=False,
                        help='Number of iterations to repeat if convergence is not reached. ',
                        default=1000)
    return parser

def manca():
    args = set_manca().parse_args()
    try:
        if args['f'] == 'graphml':
            network = nx.read_graphml(args['graph'])
        elif args['f'] == 'edgelist':
            network = nx.read_weighted_edgelist(args['graph'])
        elif args['f'] == 'gml':
            network = nx.read_gml(args['graph'])
        elif args['f'] == 'adj':
            network = nx.read_multiline_adjlist(args['graph'])
        else:
            sys.stdout.write('Format not accepted.')
            sys.stdout.flush()
            exit()
    except Exception:
        sys.stdout.write('Could not import network file! ')
        sys.stdout.flush()
        exit()
    clustered = cluster_graph(network, limit=args['limit'],
                              diff_range=args['df'], max_clusters=args['mc'],
                              iterations=args['iter'])
    if args['f'] == 'graphml':
        nx.write_graphml(clustered, args['fp'])
    elif args['f'] == 'edgelist':
        nx.write_weighted_edgelist(clustered, args['fp'])
    elif args['f'] == 'gml':
        nx.write_gml(clustered, args['fp'])
    elif args['f'] == 'adj':
        nx.write_multiline_adjlist(clustered, args['fp'])
    sys.stdout.write('Wrote clustered network to ' + args['fp'] + '.')
    sys.stdout.flush()

def cluster_graph(graph, limit=100, diff_range=3, max_clusters=5, iterations=1000):
    """
    Takes a networkx graph
    and carries out network clustering until
    sparsity results converge. Directionality is ignored;
    if weight is available, this is considered during the diffusion process.
    Setting diff_range to 1 means that the algorithm
    will basically cluster the adjacency matrix.

    Parameters
    ----------
    :param graph: Weighted, undirected networkx graph.
    :param limit: Number of iterations to run until alg considers sparsity value converged.
    :param diff_range: Diffusion range of network perturbation.
    :param max_clusters: Number of clusters to evaluate in K-means clustering.
    :param iterations: If algorithm does not converge, it stops here.
    :return: Networkx graph with cluster ID as node property.
    """
    delay = 0  # after delay reaches the limit value, algorithm is considered converged
    adj = np.zeros((len(graph.nodes), len(graph.nodes)))  # this considers diffusion, I could also just use nx adj
    adj_index = dict()
    for i in range(len(graph.nodes)):
        adj_index[list(graph.nodes)[i]] = i
    rev_index = {v: k for k, v in adj_index.items()}
    prev_sparsity = 0
    iters = 0
    while delay < limit and iters < iterations:
        node = choice(list(graph.nodes))
        # iterate over node neighbours across range
        nbs = dict()
        nbs[node] = 1.0
        upper_diff = list()
        upper_diff.append(nbs)
        for i in range(diff_range):
            # this loop specifies diffusion of weight value over the random node
            new_upper = list()
            for nbs in upper_diff:
                for nb in nbs:
                    new_nbs = graph.neighbors(nb)
                    for new_nb in new_nbs:
                        next_diff = dict()
                        try:
                            weight = graph.get_edge_data(nb, new_nb)['weight']
                        except KeyError:
                            sys.stdout.write('Edge did not have a weight attribute! Setting to 1.0')
                            sys.stdout.flush()
                            weight = 1.0
                        next_diff[new_nb] = weight * nbs[nb]
                        adj[adj_index[node], adj_index[new_nb]] += weight * nbs[nb]
                        adj[adj_index[new_nb], adj_index[node]] += weight * nbs[nb] # undirected so both sides have weight added
                        new_upper.append(next_diff)
            upper_diff = new_upper
        # next part is to define clusters of the adj matrix
        # cluster number is defined through gap statistic
        # max cluster number to test is by default 5
        # define topscore and bestcluster for no cluster
        topscore = 2
        bestcluster = None
        randomclust = np.random.randint(2, size=len(adj))
        try:
            sh_score = [silhouette_score(adj, randomclust)]
        except ValueError:
            sh_score = [0]  # the randomclust can result in all 1s or 0s which crashes
        # scaler = MinMaxScaler()
        # select optimal cluster by silhouette score
        # cluster may be arbitrarily bad before convergence
        # may scale adj mat values from 0 to 1 but scaling is probably not necessary
        for i in range(1, max_clusters+1):
            # scaler.fit(adj)
            # proc_adj = scaler.transform(adj)
            clusters = KMeans(i).fit_predict(adj)
            try:
                silhouette_avg = silhouette_score(adj, clusters)
            except ValueError:
                # if only 1 cluster label is defined this can crash
                silhouette_avg = 0
            sh_score.append(silhouette_avg)
        topscore = int(np.argmax(sh_score))
        if topscore != 0:
            bestcluster = KMeans(topscore).fit_predict(adj)
            # with bestcluster defined,
            # sparsity of cut can be calculated
            sparsity = 0
            for cluster_id in set(bestcluster):
                node_ids = list(np.where(bestcluster == cluster_id)[0])
                node_ids = [rev_index.get(item, item) for item in node_ids]
                cluster = graph.subgraph(node_ids)
                # per cluster node:
                # edges that are not inside cluster are part of cut-set
                # total cut-set should be as small as possible
                for node in cluster.nodes:
                    nbs = graph.neighbors(node)
                    for nb in nbs:
                        if nb not in node_ids:
                            # only add 1 to sparsity if it is a positive edge
                            # otherwise subtract 1
                            cut = graph.get_edge_data(node, nb)['weight']
                            if cut > 0:
                                sparsity += 1
                            else:
                                sparsity -= 1
            # print("Complete cut-set sparsity: " + sparsity)
            if prev_sparsity > sparsity:
                delay = 0
            if prev_sparsity == sparsity:
                delay += 1
            prev_sparsity = sparsity
            iters += 1
    if iters == 1000:
        sys.stdout.write('Warning: algorithm did not converge.')
        sys.stdout.flush()
    clusdict = dict()
    for i in range(len(graph.nodes)):
        clusdict[list(graph.nodes)[i]] = bestcluster[i]
    nx.set_node_attributes(graph, clusdict, 'Cluster')
    return graph

if __name__ == '__main__':
    manca()