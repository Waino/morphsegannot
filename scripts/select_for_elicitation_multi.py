#!/usr/bin/env python

import argparse
import os
import sys

import flatcat
from morphsegannot import tools, selection

METRICS = {
    'uncertainty': selection.UncertaintyMetric,
    'margin': selection.MarginMetric,
    'logp': selection.LogpMetric,
    'ifsubstrings_norm': 
        lambda: selection.IFSubstringMetric(normalize=True, namesuffix='norm'),
    'ifsubstrings_un': 
        lambda: selection.IFSubstringMetric(normalize=False, namesuffix='un'),
    'ifsubstrings_5n': 
        lambda: selection.IFSubstringMetric(normalize=True, namesuffix='5n', maxlen=5),
    'oneoffboundary': selection.OneOffBoundaryMetric,
    'morphlogp_min':
        lambda: selection.MorphLogpMetric(func=min, namesuffix='min'),
    'alphabracket_unnorm': 
        lambda: selection.AlphaBracketMetric('unnorm'),
    'alphabracket_uncert': 
        lambda: selection.AlphaBracketMetric('uncert'),
    'alphabracket_logp': 
        lambda: selection.AlphaBracketMetric('logp'),
    'category': selection.CategoryMetric,
    'nostm': selection.NoStmMetric,
    }

def get_argparser():
    parser = argparse.ArgumentParser(
        prog='select_for_elicitation.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False)
    add_arg = parser.add_argument

    add_arg('iteration', metavar='<iteration>', type=int,
            help='Iteration number')
    add_arg('outdir', metavar='<output dir>',
            help='Directory to put output')
    add_arg('metrics', metavar='<metric>', nargs='+',
            help='Name of selection metric. '
                 'Can specify multiple. '
                 'Alternatives: {}'.format(
                    ' '.join(sorted(METRICS.keys()))))

    add_arg('--pooldir', dest='pooldir',
            metavar='<dir>', default='pools/',
            help='Directory containing training pool')
    add_arg('--modeldir', dest='modeldir',
            metavar='<dir>', default='models/',
            help='Directory containing trained models')
    add_arg('--annotdir', dest='annotsdir',
            metavar='<dir>', default='annotations/',
            help='Directory containing previously collected annotations')

    add_arg('-n', dest='num_annots', type=int,
            metavar='<int>', default=50,
            help='Number of words to select. '
                 '(default: %(default)s)')
    add_arg('--override-model', dest='overridemodel',
            metavar='<modelfile>', default=None,
            help='Use specified single model for all metrics. '
                 'Useful e.g. for first iteration.')
    add_arg('--override-seen', dest='overrideseen',
            metavar='<wordfile>', default=None,
            help='Use specified single previously selected words file'
                 'for all metrics. Useful e.g. for combination strategies.')
    add_arg('--config-corpus', dest='configcorpus',
            metavar='<wordfile>', default=None,
            help='Override the corpus used for configuring the '
                 'selection metric. '
                 'Useful if not all words are in the training pool.')

    add_arg('-h', '--help', action='help',
            help="show this help message and exit")
    return parser


def main(argv):
    parser = get_argparser()
    args = parser.parse_args(argv)
    io = flatcat.FlatcatIO(encoding='utf-8')

    if not args.outdir[-1] == '/':
        args.outdir += '/'
    if not os.path.exists(args.outdir):
        os.makedirs(args.outdir)

    # single model overriding the metric-specific ones
    overridemodel = None
    if not args.overridemodel is None:
        print('Loading overridemodel...')
        overridemodel = io.read_tarball_model_file(args.overridemodel)
        print('...done')
        overridemodel.initialize_hmm()  # FIXME: automate

    nonword_filename = os.path.join(
        args.annotsdir,
        '{}.nonword.words'.format(args.iteration))
    if not os.path.exists(nonword_filename):
        print('No nonword file ({}), assuming all words are valid'.format(
            nonword_filename))
        nonword_filename = None

    for metric_name in args.metrics:
        print('Metric: {}'.format(metric_name))
        metric = METRICS[metric_name]()
        # workaround for metric needing high and low models
        if metric_name.startswith('alphabracket'):
            metric.set_models(
                io.read_tarball_model_file(
                    os.path.join(
                        args.modeldir,
                        '{}.flatcat.{}_low.model.tar.gz'.format(
                            args.iteration, 'alphabracket'))),
                io.read_tarball_model_file(
                    os.path.join(
                        args.modeldir,
                        '{}.flatcat.{}_hi.model.tar.gz'.format(
                            args.iteration, 'alphabracket'))))

        if args.overrideseen is None:
            annot_filename = os.path.join(
                args.annotsdir,
                '{}.train.{}.annotated.words'.format(
                    args.iteration - 1, metric_name))
        else:
            annot_filename = args.overrideseen
        model_filename = None
        for filename in os.listdir(args.modeldir):
            if not filename.startswith(
                    '{}.flatcat.{}.'.format(args.iteration, metric_name)):
                continue
            if not filename.endswith('.model.tar.gz'):
                continue
            if model_filename is not None:
                raise Exception(
                    'Both "{}" and "{}" match the model pattern'.format(
                        model_filename, filename))
            model_filename = os.path.join( args.modeldir, filename)
        if model_filename is None and args.overridemodel is None:
            raise Exception('Model for metric "{}" not found'.format(
                metric_name))
        selection_filename = os.path.join(
            args.outdir,
            '{}.train.{}.selected'.format(args.iteration, metric_name))
        scores_filename = os.path.join(
            args.outdir,
            '{}.train.{}.scores'.format(args.iteration, metric_name))

        if os.path.exists(annot_filename):
            seen = set(tools.read_wordlist(annot_filename))
        else:
            print('No annotations file ({})'.format(annot_filename))
            seen = set()

        if not nonword_filename is None:
            nonwords = tools.read_wordlist(nonword_filename)
        else:
            nonwords = []
        seen.update(nonwords)
        if not overridemodel is None:
            model = overridemodel
        elif metric_name.startswith('alphabracket'):
            model = None
        else:
            model = io.read_tarball_model_file(model_filename)
            model.initialize_hmm()
        trainpool = tools.get_pools(['train'], args.pooldir).next()

        # already selected words (incl nonwords) cannot be reselected
        trainpool = tools.filter_pool(trainpool, seen)


        # perform selection
        selector = selection.Selector(
            metric, model,
            progress=flatcat.utils._generator_progress)
        if args.configcorpus is not None:
            print('Configuring metric with "{}"'.format(args.configcorpus))
            selector.configure(
                tools.read_wordlist(args.configcorpus),
                seen=seen)
        print('Performing ranking...')
        ranked = selector.rank(trainpool, seen=seen, n=args.num_annots)
        print('...done')

        # write
        selection.write_selected(ranked, selection_filename, args.num_annots)
        selection.write_scores(ranked, scores_filename)


if __name__ == "__main__":
    main(sys.argv[1:])
