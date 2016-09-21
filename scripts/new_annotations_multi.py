#!/usr/bin/env python

import argparse
import itertools
import os
import sys

from morphsegannot import tools


def get_argparser():
    parser = argparse.ArgumentParser(
        prog='new_annotations.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('newfile', metavar='<new annotation file>',
            help='Annotation log containing new annotations')
    add_arg('oldfile', metavar='<old annotation file>',
            help='File containing old annotations')
    add_arg('outdir', metavar='<output dir>',
            help='Directory to put output')
    add_arg('iteration', metavar='<iteration>',
            help='Iteration number')
    add_arg('metrics',
            metavar='<metric>', nargs='*',
            help='Selection metrics. '
                 'Can specify zero or more.')

    add_arg('--all-metrics', dest='allmetrics',
            action='store_true',
            help='Use all metrics in selections directory')

    add_arg('--selectiondir', dest='selectiondir',
            metavar='<dir>', default='selections/',
            help='Directory containing selections')
    add_arg('--pools', dest='pools',
            metavar='<list>', default='dev,test',
            help='Static pools, separated by comma')
    add_arg('--pooldir', dest='pooldir',
            metavar='<dir>', default='pools/',
            help='Directory containing pools')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    nonwords = set()
    if args.newfile == '-':
        new_annots = []
    else:
        (new_annots, new_nonwords) = tools.read_annotation_log(args.newfile)
        nonwords.update(new_nonwords)

    if args.oldfile == '-':
        old_annots = []
    else:
        (old_annots, old_nonwords) = tools.read_old_annotations(args.oldfile)
        nonwords.update(old_nonwords)

    pools = tools.get_pools(args.pools.split(','),
                            args.pooldir)
                            # FIXME: suffixes
    if len(args.metrics) > 0 or args.allmetrics:
        if args.allmetrics:
            metrics = tools.all_metrics(args.selectiondir,
                                        args.iteration,
                                        args.pools.split(','))
            print('Found metrics: {}'.format(', '.join(metrics)))
        else:
            metrics = args.metrics
        selections = tools.get_selections(metrics,
                                          args.selectiondir,
                                          args.iteration)
        pools = itertools.chain(pools, selections)

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    pipe = tools.combine_with_old_annotations(
        pools, old_annots, new_annots, nonwords)
    mfaw = tools.MultiFileAnnotationWriter(
        '{}{}.'.format(args.outdir, args.iteration),
        '')    # FIXME: suffix
    mfaw.write(pipe)


if __name__ == "__main__":
    main(sys.argv[1:])
