#!/usr/bin/env python

from __future__ import unicode_literals

import argparse
import codecs
import os
import sys

from morphsegannot.tools import tools


def get_argparser():
    parser = argparse.ArgumentParser(
        prog='compare_annotators.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('infiles', metavar='<annotation file>', nargs=2,
            help='File containing annotations')
    add_arg('--outdir', metavar='<output dir>',
            default='annotator_comparison',
            help='Directory to put output')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def seg_to_boundaries(seg):
    boundaries = []
    for morph in seg:
        boundaries.extend((len(morph) - 1) * [False])
        boundaries.append(True)
    boundaries.pop()
    return boundaries


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    annots = []
    for filename in args.infiles:
        (tmp, _) = tools.read_old_annotations(filename)
        annots.append({a.word: a.analysis for a in tmp})

    common = set.intersection(*(set(a.keys())
                                for a in annots))
    print('{} common words'.format(len(common)))

    samepath = os.path.join(args.outdir, 'same.segmentations')
    diffpath = os.path.join(args.outdir, 'diff.segmentations')
    w_samecount = 0
    w_diffcount = 0
    b_samecount = 0
    b_diffcount = 0
    a_pos = 0
    a_neg = 0
    b_pos = 0
    b_neg = 0
    with codecs.open(samepath, 'w', encoding='utf-8') as samefobj:
        with codecs.open(diffpath, 'w', encoding='utf-8') as difffobj:
            for word in common:
                aa = annots[0][word]
                bb = annots[1][word]
                if aa == bb:
                    samefobj.write('{}\t{}\n'.format(
                        word,
                        tools._format_analysis(aa)))
                    w_samecount += 1
                    #b_samecount += len(word) - 1
                else:
                    difffobj.write('{}\n'.format(word))
                    for a in annots:
                        difffobj.write('\t{}\n'.format(
                            tools._format_analysis(a[word])))
                    w_diffcount += 1
                for (a, b) in zip(seg_to_boundaries(aa),
                                  seg_to_boundaries(bb)):
                    a_pos += a
                    a_neg += not a
                    b_pos += b
                    b_neg += not b
                    b_samecount += (a == b)
                    b_diffcount += (a != b)
    w_agreement = float(w_samecount) / (w_samecount + w_diffcount)
    print('words:\t\t{} same, {} different, {} agreement'.format(
        w_samecount, w_diffcount, w_agreement))
    obs_agreement = float(b_samecount) / (b_samecount + b_diffcount)
    print('boundaries:\t{} same, {} different, {} agreement'.format(
        b_samecount, b_diffcount, obs_agreement))
    p_a = float(a_pos) / (a_pos + a_neg)
    p_b = float(b_pos) / (b_pos + b_neg)
    p_eq = (p_a * p_b) + ((1. - p_a) * (1. - p_b))
    print('p(a) = {}, p(b) = {}, p(a == b) = {}'.format(p_a, p_b, p_eq))
    kappa = (obs_agreement - p_eq) / (1. - p_eq)
    print('Cohens kappa: {}'.format(kappa))


if __name__ == "__main__":
    main(sys.argv[1:])
