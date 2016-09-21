#!/usr/bin/env python

import argparse
import os
import sys

from morphsegannot.tools import tools

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='new_annotations.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('iteration', metavar='<iteration>',
            help='Current iteration number')
    add_arg('metric',
            metavar='<metric>',
            help='Selection metric (for output).')
    add_arg('newfile', metavar='<new annotation log>',
            help='Annotation log containing newly elicited annotations')
    add_arg('oldfile', metavar='<old train file>',
            help='File containing annotated training data '
                 'from previous iteration. "-" for none.')
    add_arg('selectionfile', metavar='<selected words>',
            help='File containing all selections '
                 'from current iteration '
                 '(including non-re-elicited)')

    add_arg('--outdir', dest='outdir',
            metavar='<output dir>', default='train/',
            help='Directory to put output. '
                 '(default: %(default)s)')

    add_arg('--old-oracle', dest='oldoracle',
            metavar='<annotfile>', default=None,
            help='Old annotations from the oracle. '
                 'These can be re-selected, but are not re-elicited. '
                 'Useful if restarting the experiment.')

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

    old_oracle = []
    if args.oldoracle is not None:
        (old_oracle, old_nonwords) = tools.read_old_annotations(
            args.oldoracle)
        nonwords.update(old_nonwords)

    selections = tools.read_wordlist(args.selectionfile)

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    pipe = tools.combine_single(
        new_annots, selections, old_annots, old_oracle, nonwords, args.metric)
    mfaw = tools.MultiFileAnnotationWriter(
        '{}{}.'.format(args.outdir, args.iteration),
        '')
    mfaw.write(pipe)


if __name__ == "__main__":
    main(sys.argv[1:])
