#!/usr/bin/env python

import argparse
import collections
import os
import re
import sys

from morphsegannot.tools import tools

RE_UNTAG = re.compile(r'/[A-Z][A-Z][A-Z]')

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='process_single_iteration.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('--pooldir', dest='pooldir',
            metavar='<dir>', default='data/input/',
            help='Directory containing pools. '
                 '(default: %(default)s)')
    add_arg('--gendir', dest='gendir',
            metavar='<dir>', default='data/generated/',
            help='Directory containing selections. '
                 '(default: %(default)s)')
    add_arg('--logdir', dest='logdir',
            metavar='<dir>', default='data/output/',
            help='Directory with annotation logs and our output. '
                 '(default: %(default)s)')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def write_both(pool, annots, basename):
    with open(basename + '.tagged', 'w') as taggedfobj:
        with open(basename, 'w') as unfobj:
            for word in pool:
                if word not in annots:
                    print('{} not in annots'.format(word))
                    continue
                analyses = [tools._format_analysis(analysis)
                            for analysis in annots[word]]
                tagged = ', '.join(analyses)
                taggedfobj.write('{}\t{}\n'.format(word, tagged))
                untagged = RE_UNTAG.sub('', tagged)
                unfobj.write('{}\t{}\n'.format(word, untagged))

def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)

    # This tool can only handle a single iteration of IFSubstrings
    # If you want to use the other strategies, look at the other scripts
    iteration = 1
    metric = 'ifsubstrings_5n'

    # read in all annotations
    # make sure to allow multiple variants
    fnames = []
    for fname in os.listdir(args.logdir):
        if fname.startswith('annotations_') and \
                fname.endswith('_{}.txt'.format(iteration)):
            fnames.append(fname)
    if len(fnames) == 0:
        raise Exception('Did not find any annotations for iteration '
                        '{} in {}'.format(iteration, args.logdir))
    elif len(fnames) > 1:
        print('WARNING')
        print('Found multiple annotations. Combining them all.')
    #    (old_annots, old_nonwords) = tools.read_old_annotations(args.oldfile)

    annots = collections.defaultdict(list)
    nonwords = set()
    for fname in fnames:
        print(fname)
        (new_annots, new_nonwords) = tools.read_annotation_log(
            os.path.join(args.logdir, fname))
        nonwords.update(new_nonwords)
        for annot in new_annots:
            annots[annot.word].append(annot.analysis)

    # read in pools (dev, test) and selections
    # for each, retrieve the annotations and write to appropriate file
    devpool = tools.read_wordlist(
        os.path.join(args.pooldir, 'devpool.words'))
    write_both(devpool, annots,
               os.path.join(args.logdir, 'dev.annots'))

    testpool = tools.read_wordlist(
        os.path.join(args.pooldir, 'testpool.words'))
    write_both(testpool, annots,
               os.path.join(args.logdir, 'test.annots'))

    selections = tools.read_wordlist(
        os.path.join(args.gendir,
        '{}.train.{}.all.selected'.format(iteration, metric)))
    write_both(selections, annots,
               os.path.join(args.logdir,
                            '{}.{}.annots'.format(iteration, metric)))

if __name__ == "__main__":
    main(sys.argv[1:])
