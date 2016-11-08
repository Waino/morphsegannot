from __future__ import unicode_literals

import codecs
import collections
import math

WordFeatures = collections.namedtuple('WordFeatures', ['word', 'f'])
ScoredWord = collections.namedtuple('ScoredWord', ['score', 'word'])


class Selector(object):
    def __init__(self, metric, model, progress=None):
        self.metric = metric
        self.model = model
        self.need_nbest = metric.need_nbest
        self.need_forward = metric.need_forward
        self._progress = progress

    def calculate_features(self, words):
        if self._progress is not None:
            words = self._progress(words)
        for word in words:
            features = collections.defaultdict(dict)
            viterbi = None
            if self.need_nbest == 0:
                pass
            elif self.need_nbest == 1:
                morphs, viterbi_logp = self.model.viterbi_analyze(word)
                viterbi = [(morphs, viterbi_logp)]
            else:
                viterbi = self.model.viterbi_nbest(word, self.need_nbest)
            if not viterbi is None:
                features['generic']['viterbi'] = viterbi

            if self.need_forward:
                forward_logp = self.model.forward_logprob(word)
                features['generic']['forward_logp'] = forward_logp

                features['uncertainty'] = (
                    features['generic']['viterbi'][0][1]
                    - features['generic']['forward_logp'])

            custom = self.metric.features(word, features)
            if custom is not None:
                features[self.metric.name] = custom

            yield WordFeatures(word, features)

    def configure(self, words, seen=None):
        try:
            self.metric.configure(words, seen, self.model)
        except AttributeError:
            pass

    def rank(self, words, seen=None, n=None):
        try:
            words = list(words.words)
        except AttributeError:
            words = list(words)
        try:
            if not self.metric.configured:
                self.metric.configure(words, seen, self.model)
                print('Used training pool to configure')
        except AttributeError:
            pass
        features = list(self.calculate_features(words))
        scored = self.metric.rank(features, n)
        return scored


class AbstractMetric(object):
    need_nbest = 1
    need_forward = False
    descending = False
    configured = False

    @staticmethod
    def features(word, features):
        return None

    def score(self, features):
        raise Exception('Not implemented')

    def rank(self, features, n=None):
        scored = self.score(features)
        scored = sorted(scored, reverse=self.descending)
        return scored


class UncertaintyMetric(AbstractMetric):
    """Chooses words based on
    the uncertainty of the current model,
    given by viterbi prob / forward prob
    """
    name = 'uncertainty'
    need_nbest = 1
    need_forward = True
    descending = True

    @classmethod
    def score(self, wfeatures):
        for wfeature in wfeatures:
            yield ScoredWord(wfeature.f[self.name],
                             wfeature.word)


class MarginMetric(AbstractMetric):
    """Chooses words based on
    the margin between best and secondbest
    """
    name = 'margin'
    need_nbest = 2
    need_forward = True
    descending = False

    @classmethod
    def score(self, wfeatures):
        for wfeature in wfeatures:
            if len(wfeature.f['generic']['viterbi']) < 2:
                # no second option
                continue
            best = wfeature.f['generic']['viterbi'][0][1]
            scnd = wfeature.f['generic']['viterbi'][1][1]
            fwd  = wfeature.f['generic']['forward_logp']
            yield ScoredWord(
                ((math.exp(-best) - math.exp(-scnd))
                 / math.exp(-fwd)),
                wfeature.word)


class LogpMetric(AbstractMetric):
    """Chooses words based on
    the logp normalized by number of chars
    """
    name = 'logp'
    need_nbest = 1
    need_forward = False
    descending = True   # we want the least likely

    @classmethod
    def score(self, wfeatures):
        for wfeature in wfeatures:
            logp = wfeature.f['generic']['viterbi'][0][1]
            yield ScoredWord(logp / len(wfeature.word),
                             wfeature.word)


class IFSubstringMetric(AbstractMetric):
    """Chooses words based on
    maximizing the coverage of initial and final substrings.
    Already seen substrings are not rewarded.
    """
    need_nbest = 0
    need_forward = False
    descending = True

    def __init__(self, normalize=True, namesuffix='std', maxlen=5):
        self.name = 'ifsubstrings_{}'.format(namesuffix)
        self.normalize = normalize

        self.i_substrings = None
        self.f_substrings = None

        self.minlen = 2
        self.maxlen = maxlen

        # temporary masks for newly selected substrings
        # during ranking
        self.i_mask = set()
        self.f_mask = set()

    def configure(self, words, seen, model=None):
        # FIXME: should we be counting substrs from unannotated corpus?
        self.i_substrings = collections.Counter()
        self.f_substrings = collections.Counter()
        for word in words:
            (initial, final) = self._substrings(word)
            for sub in initial:
                self.i_substrings[sub] += 1
            for sub in final:
                self.f_substrings[sub] += 1
        if self.normalize:
            self._normalize(self.i_substrings)
            self._normalize(self.f_substrings)
        # zeroing seen substrings (could add malus also)
        if seen is not None:
            for word in seen:
                (initial, final) = self._substrings(word)
                for sub in initial:
                    self.i_substrings[sub] = 0
                for sub in final:
                    self.f_substrings[sub] = 0
        self.configured = True

    @staticmethod
    def _normalize(substrings):
        # normalize by average count for substring length
        sum_by_len = collections.Counter()
        count_by_len = collections.Counter()
        for (sub, count) in substrings.items():
            sum_by_len[len(sub)] += count
            count_by_len[len(sub)] += 1
        for sub in substrings.keys():
            substrings[sub] /= float(sum_by_len[len(sub)])
            substrings[sub] *= float(count_by_len[len(sub)])

    def _substrings(self, word):
        initial = []
        final = []
        end = min(self.maxlen, len(word)) + 1
        for i in range(self.minlen, end):
            initial.append(word[:i])
            final.append(word[-i:])
        return (initial, final)


    def features(self, word, features):
        # features change during ranking
        return None

    def score(self, wfeatures):
        for wfeature in wfeatures:
            i_score = 0
            f_score = 0
            (initial, final) = self._substrings(wfeature.word)
            for sub in initial:
                if sub not in self.i_mask:
                    i_score += self.i_substrings[sub]
            for sub in final:
                if sub not in self.f_mask:
                    f_score += self.f_substrings[sub]
            yield ScoredWord(i_score + f_score,
                             wfeature.word)

    def rank(self, words, n):
        assert n is not None, 'IFSubstringMetric requires n'
        scored = []
        self.i_mask = set()
        self.f_mask = set()
        while len(scored) < n and len(words) > 0:
            (best, words) = self._select_best(words)
            scored.append(best)
        return scored

    def _select_best(self, words):
        scored = self.score(words)
        scored = sorted(scored, reverse=self.descending)
        selected = scored.pop(0)
        (initial, final) = self._substrings(selected.word)
        for sub in initial:
            self.i_mask.add(sub)
        for sub in final:
            self.f_mask.add(sub)
        return (selected, scored)


class OneOffBoundaryMetric(AbstractMetric):
    """Chooses words based on
    morphs x = yc or cy,
    weighted by frequency, with uncertainty as tiebreaker.
    """
    need_nbest = 1
    need_forward = True     # needed by uncertainty
    descending = True

    max_len = 8

    def __init__(self, namesuffix='std'):
        self.name = 'oneoffboundary_{}'.format(namesuffix)

    def configure(self, words, seen, model):
        # weights assigned to morphs
        self.weights = collections.defaultdict(int)
        # temporary mask for newly selected substrings
        # during ranking
        self.mask = set()

        by_length = collections.defaultdict(dict)
        seen_max = 0
        for morph, counts in model.get_lexicon():
            if len(morph) > self.max_len:
                continue
            by_length[len(morph)][morph] = sum(counts)
            seen_max = max(seen_max, len(morph))
        for i in range(2, seen_max + 1):
            for (morph, count_longer) in by_length[i].items():
                submorph = morph[1:]
                if submorph in by_length[i - 1]:
                    weight = count_longer * by_length[i - 1][submorph]
                    self.weights[morph] += weight
                    self.weights[submorph] += weight
                    #print(morph, submorph, weight)
                submorph = morph[:-1]
                if submorph in by_length[i - 1]:
                    weight = count_longer * by_length[i - 1][submorph]
                    self.weights[morph] += weight
                    self.weights[submorph] += weight
                    #print(morph, submorph, weight)

        # zeroing seen morphs (could add malus also)
        if seen is not None:
            for word in seen:
                morphs, _ = model.viterbi_analyze(word)
                for morph in morphs:
                    self.weights[morph.morph] = 0
        self.configured = True

    def features(self, word, features):
        # features change during ranking
        return None

    def score(self, wfeatures):
        for wfeature in wfeatures:
            score = 0
            for cmorph in wfeature.f['generic']['viterbi'][0][0]:
                morph = cmorph.morph
                if morph not in self.mask:
                    score += self.weights[morph]
            assert 'uncertainty' in wfeature.f
            yield ScoredWord((score, wfeature.f['uncertainty']),
                             wfeature)

    def rank(self, words, n):
        assert n is not None, 'OneOffBoundaryMetric requires n'
        scored = []
        self.mask = set()
        while len(scored) < n and len(words) > 0:
            (best, words) = self._select_best(words)
            scored.append(ScoredWord(
                best.score,
                best.word.word))
        return scored

    def _select_best(self, words):
        scored = self.score(words)
        scored = sorted(scored, reverse=self.descending)
        selected = scored.pop(0)
        for cmorph in selected.word.f['generic']['viterbi'][0][0]:
            morph = cmorph.morph
            self.mask.add(morph)
        return (selected, [x.word for x in scored])


class MorphLogpMetric(AbstractMetric):
    """Chooses words based on
    the morph with min/max emission logp
    with uncertainty as tiebreaker.
    """
    need_nbest = 1
    need_forward = True     # needed by uncertainty
    descending = True

    def __init__(self, func=min, namesuffix='std'):
        self.func = func
        self.name = 'morphlogp_{}'.format(namesuffix)
        self.model = None

    def configure(self, words, seen, model):
        self.model = model
        self.configured = True

    def features(self, word, features):
        analysis = features['generic']['viterbi'][0][0]
        emissions = [self.model._corpus_coding.log_emissionprob(
                        cmorph.category, cmorph.morph)
                     for cmorph in analysis]
        return emissions

    def score(self, wfeatures):
        for wfeature in wfeatures:
            score = self.func(wfeature.f[self.name])
            assert 'uncertainty' in wfeature.f
            yield ScoredWord((score, wfeature.f['uncertainty']),
                             wfeature.word)


class AlphaBracketMetric(AbstractMetric):
    """Chooses words based on disagreement between
    two models with different alpha,
    with sum of logp:s normalized by length in chars as ranker.
    """
    need_nbest = 0
    need_forward = False
    descending = False  # return most probable disagreed word

    def __init__(self, namesuffix='logp'):
        self.name = 'alphabracket_{}'.format(namesuffix)
        self.variant = namesuffix
        self.model_low = None
        self.model_hi = None

    def set_models(self, low, hi):
        self.model_low = low
        self.model_hi = hi
        self.model_low.initialize_hmm()
        self.model_hi.initialize_hmm()

    def features(self, word, features):
        morphs_low, logp_low = self.model_low.viterbi_analyze(word)
        morphs_hi, logp_hi = self.model_hi.viterbi_analyze(word)
        if self.variant == 'unnorm':
            # unnormalized logp
            low = logp_low
            hi = logp_hi
        elif self.variant == 'uncert':
            # uncertainty
            low_forward_logp = self.model_low.forward_logprob(word)
            hi_forward_logp = self.model_hi.forward_logprob(word)
            low = logp_low - low_forward_logp
            hi = logp_hi - hi_forward_logp
        else:
            # normalized logp
            low = logp_low / len(word)
            hi = logp_hi / len(word)
        return {'low': low,
                'hi': hi,
                'match': (morphs_low == morphs_hi)}

    def score(self, wfeatures):
        for wfeature in wfeatures:
            if wfeature.f[self.name]['match']:
                # filter out matching words
                continue
            score = wfeature.f[self.name]['hi'] + wfeature.f[self.name]['low']
            yield ScoredWord(score, wfeature.word)


class CategoryMetric(AbstractMetric):
    """Chooses words based on
    presence of subsequent SUF/ZZZ
    with uncertainty as ranker.
    """
    name = 'category'
    need_nbest = 1
    need_forward = True     # needed by uncertainty
    descending = True

    def features(self, word, features):
        analysis = features['generic']['viterbi'][0][0]
        categories = [cmorph.category for cmorph in analysis]
        match = False
        for (prev, nxt) in zip(categories, categories[1:]):
            if prev not in ('STM', 'ZZZ'):
                continue
            if nxt not in ('STM', 'ZZZ'):
                continue
            return True
        return False

    def score(self, wfeatures):
        for wfeature in wfeatures:
            if not wfeature.f[self.name]:
                # filter out words without pattern
                continue
            assert 'uncertainty' in wfeature.f
            yield ScoredWord(wfeature.f['uncertainty'],
                             wfeature.word)


class NoStmMetric(AbstractMetric):
    """Chooses words based on
    lack of STM tagged morph,
    with uncertainty as ranker.
    """
    name = 'nostm'
    need_nbest = 1
    need_forward = True     # needed by uncertainty
    descending = True

    def features(self, word, features):
        analysis = features['generic']['viterbi'][0][0]
        categories = [cmorph.category for cmorph in analysis]
        return 'STM' in categories

    def score(self, wfeatures):
        for wfeature in wfeatures:
            if wfeature.f[self.name]:
                # filter  words with stm
                continue
            assert 'uncertainty' in wfeature.f
            yield ScoredWord(wfeature.f['uncertainty'],
                             wfeature.word)


def write_scores(ranked, filename):
    """Debug function to write all scores out into file"""
    with codecs.open(filename, 'w', encoding='utf-8') as fobj:
        for score in ranked:
            fobj.write('{}\t{}\n'.format(score.word, score.score))

def write_selected(ranked, filename, n):
    selected = []
    with codecs.open(filename, 'w', encoding='utf-8') as fobj:
        for score in ranked[:n]:
            fobj.write('{}\n'.format(score.word))
            selected.append(score.word)
    return selected


LOGPROB_ZERO = 1000000
def zlog(x):
    """Logarithm which uses constant value for log(0) instead of -inf"""
    assert x >= 0.0
    if x == 0:
        return LOGPROB_ZERO
    return -math.log(x)
