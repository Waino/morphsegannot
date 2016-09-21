#!/usr/bin/env python

from __future__ import unicode_literals

import argparse
import codecs
import itertools
import os
import sys

import flatcat
from morphsegannot import tools


def get_argparser():
    parser = argparse.ArgumentParser(
        prog='paste_annotations.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('annotfile', metavar='<annotation file>',
            help='File containing all annotations')
    add_arg('outdir', metavar='<output dir>',
            help='Directory to put output')

    add_arg('--annotdir', dest='annotdir',
            metavar='<dir>', default=None,
            help='Combine with old annots from this dir.')
    add_arg('-i', '--iteration', dest='iteration',
            metavar='<iteration>', type=int, default=None,
            help='Iteration number')

    add_arg('--selectiondir', dest='selectiondir',
            metavar='<dir>', default='selections/',
            help='Directory containing selections')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    (annots, _) = tools.read_old_annotations(args.annotfile)
    annots = {a.word: a.analysis for a in annots}

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    for filename in os.listdir(args.selectiondir):
        if not filename.endswith('.selected'):
            continue
        path = os.path.join(args.selectiondir, filename)
        outfilename = filename.replace('.selected',
                                       '.goldstd.segmentation')
        outpath = os.path.join(args.outdir, outfilename)

        words = tools.read_wordlist(path)
        if args.annotdir is not None and args.iteration is not None:
            annotfilename = filename.replace('.selected',
                                             '.annotated.words')
            annotfilename = annotfilename.replace(
                str(args.iteration),
                str(int(args.iteration) - 1),
                1)
            annotpath = os.path.join(args.annotdir, annotfilename)
            if os.path.exists(annotpath):
                oldwords = tools.read_wordlist(annotpath)
                words = itertools.chain(oldwords, words)
            else:
                print('No old annotations "{}"'.format(annotpath))

        with codecs.open(outpath, 'w', encoding='utf-8') as fobj:
            for word in words:
                if word not in annots:
                    print('No annotation for {}'.format(word))
                    continue
                # FIXME redundancy
                fobj.write('{}\t{}\n'.format(
                    word, 
                    tools._format_analysis(
                        flatcat.FlatcatModel.detag_word(annots[word]))))


if __name__ == "__main__":
    main(sys.argv[1:])
