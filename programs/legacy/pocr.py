import sys
import os
import re
import collections
from bisect import bisect
from textwrap import dedent
from itertools import chain

from Levenshtein import ratio

from tf.core.helpers import unexpanduser
from tf.advanced.helpers import dm
from config import Config
from tfFromTsv import loadTf


CONSONANT_RE = re.compile(r"""[bcdfghjklmnpqrstvwxz]{2}""")


def makeInterval(low, high, nIntervals):
    """Divide an interval into subintervals logarithmically.

    Parameters
    ----------
    low: integer >= 0
        Start of the interval
    high: integer > low
        End of the interval (inclusive)
    nIntervals: integer > 0
        maximum amount of intervals to create.
        It could be that we need less, because we will skip intervals
        that are less than 1 apart.

    Returns
    -------
    list
        The values between low and high (inclusive) where a new interval starts
    """
    useLow = max((1, low))
    factor = high / useLow
    increase = factor ** (1 / nIntervals)
    points = [low, 1] if low == 0 else [low]
    curPoint = useLow
    for i in range(nIntervals):
        nextPoint = curPoint * increase
        nextInt = int(round(nextPoint))
        if nextInt > high:
            break
        curPoint = nextPoint
        if nextInt == points[-1]:
            continue
        points.append(nextInt)
    return points


def showDistributionFreq(data, itemLabel, amountLabel, maxBuckets=50, maxAmounts=80):
    """Show a frequency distribution of data with exponentially growing buckets.

    Parameters
    ----------
    data: dict
        the keys are frequencies and the values are the amounts of items
        that have that frequency.
    itemLabel: string
        the name of the items whose frequency distribution is displayed
    amountLabel: string
        how the frequency should be labelled
    maxBuckets: integer, optional 50
        maximum number of distinct buckets
    maxAmounts: integer, optional 80
        maximum number of distinct amounts

    The function shows a display of buckets of frequencies of items
    and the amount of items in those buckets.

    The buckets are logarithmically divided over the frequency space,
    because the distributions are typically exponential.
    We choose up to maxBuckets intervals from the lowest frequency to the highest.
    When buckets are less than 1 apart, we skip them.

    Likewise, the amounts in the buckets are plotted logarithmically,
    in at most maxAmounts intervals.

    Example:

    ```
    data = {
        1: 50,
        2: 40,
        5: 20,
        10: 10,
        83: 12,
        257: 9,
        1012: 8,
        10000: 4,
        10350: 3,
        11000: 16,
        12500: 1,
    }

    showDistributionFreq(data, "items", "freq")

    freq │items
    ─────┼──────────────────────────────────────────────────────────────────────────────────
    12500│■1
    10351│■■■■■■■■■■■■■■■■16
     8571│■■■■■■■7
      891│■■■■■■■■8
      238│■■■■■■■■■9
       77│■■■■■■■■■■■■12
       10│■■■■■■■■■■10
        5│■■■■■■■■■■■■■■■■■■■■20
        2│■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■40
        1│■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■50
    ```
    """

    minFreq = min(data)
    maxFreq = max(data)
    lenBucketInt = len(str(maxFreq))
    bucketPoints = makeInterval(minFreq, maxFreq, maxBuckets)

    buckets = collections.Counter()

    for (freq, nItems) in data.items():
        bucketIndex = bisect(bucketPoints, freq) - 1
        bucket = bucketPoints[bucketIndex]
        buckets[bucket] += nItems

    minAmount = min(buckets.values())
    maxAmount = max(buckets.values())
    lenAmountInt = len(str(maxAmount))
    amountPoints = makeInterval(minAmount, maxAmount, maxAmounts)

    lines = []
    labelLength = max((len(amountLabel), lenBucketInt))
    valueLength = max((len(itemLabel), maxAmounts + lenAmountInt))

    lines.append(f"{amountLabel:<{labelLength}}│{itemLabel}")
    lines.append("─" * labelLength + "┼" + "─" * valueLength)

    for (bucket, nItems) in sorted(buckets.items(), key=lambda x: -x[0]):
        valueIndex = bisect(amountPoints, nItems)
        valueRep = "■" * valueIndex + str(nItems)
        lines.append(f"{bucket:>{labelLength}}│{valueRep}")
    print("\n".join(lines))


def showDistribution(data, itemLabel, amountLabel, maxAmounts=80, legend={}):
    """Show a distribution of data with in buckets.

    Parameters
    ----------
    data: dict
        the keys are buckets and the values are the amounts of items in that bucket
    itemLabel: string
        the name of the items in the bucket
    amountLabel: string
        how the buckets should be labelled
    maxAmounts: integer, optional 80
        maximum number of distinct amounts

    The function shows a display of buckets of items
    and the amount of items in those buckets.

    The amounts in the buckets are plotted logarithmically,
    in at most maxAmounts intervals.
    """

    lenBucket = max(len(str(legend.get(bucket, bucket))) for bucket in data)

    buckets = collections.Counter()

    for (bucket, nItems) in sorted(data.items()):
        buckets[str(legend.get(bucket, bucket))] += nItems

    minAmount = min(buckets.values())
    maxAmount = max(buckets.values())
    lenAmountInt = len(str(maxAmount))
    amountPoints = makeInterval(minAmount, maxAmount, maxAmounts)

    lines = []
    labelLength = max((len(amountLabel), lenBucket))
    valueLength = max((len(itemLabel), maxAmounts + lenAmountInt))

    lines.append(f"{amountLabel:<{labelLength}}│{itemLabel}")
    lines.append("─" * labelLength + "┼" + "─" * valueLength)

    for (bucket, nItems) in buckets.items():
        valueIndex = bisect(amountPoints, nItems)
        valueRep = "■" * valueIndex + str(nItems)
        lines.append(f"{bucket:>{labelLength}}│{valueRep}")
    print("\n".join(lines))


def kindRep(kind):
    return "" if kind is None else "-start" if kind is False else "-end"


def isTrueBi(gram):
    return not (len(gram) == 3 and gram[0] == "├" and gram[-1] == "┤")


NS = (2, 3)

CHAR_CLASSES = """
*0 •™_~"[
i1 fijklrtBDEFIJKLPRT1!ïÈÉËÏ£|!\
i2 nhuHNUüÜ«°]
i3 mM
o1 abdgopqOQ690óöÓÖ()»}#&><^
c1 ecCGèéêë€*®?
v1 vxyVXY
v2 ww
s1 sS5$§
z1 zZ
21 2%
a1 A
"""

CONFUSIONS = """
├H 't
"""


class PostOcr:
    def __init__(self, volume):
        self.volume = volume
        self.good = self.config()
        self.loadTf()
        self.getWords()
        # self.initOcrKey()
        # self.getGrams()

    def config(self):
        """Configure context information."""
        volume = self.volume

        C = Config()
        if not C.checkVolume(volume):
            return False

        self.C = C
        postDir = f"{C.postDir}/{C.volumeNameNum(volume)}"
        if not os.path.exists(postDir):
            os.makedirs(postDir, exist_ok=True)
        self.postDir = postDir

    def loadTf(self):
        """Load corpus into Text-Fabric."""
        volume = self.volume
        print("Loading TF data ...")
        TF = loadTf(volume, silent=True)
        self.TF = TF
        print("done")

    def getWords(self):
        TF = self.TF
        F = TF.api.F
        postDir = self.postDir

        WORD_OCCS = collections.defaultdict(list)
        self.WORD_OCCS = WORD_OCCS

        for w in F.otype.s("word"):
            word = F.letters.v(w)
            WORD_OCCS[word].append(w)
        print(f"{len(WORD_OCCS)} words in {F.otype.maxSlot} occurrences")

        filePath = f"{postDir}/wordfreqs.tsv"
        with open(filePath, "w") as fh:
            fh.write("freq\tword\n")
            for (word, occs) in sorted(WORD_OCCS.items(), key=lambda x: x[0]):
                fh.write(f"{len(occs)}\t{word}\n")
        print(f"All words frequencies written to {unexpanduser(filePath)}")

        wordDist = collections.Counter()
        for occs in WORD_OCCS.values():
            wordDist[len(occs)] += 1
        showDistributionFreq(wordDist, "word occurrence", "word frequency")

    def getCharacters(self):
        WORD_OCCS = self.WORD_OCCS

        CHARS = collections.Counter()
        self.CHARS = CHARS

        for (word, occs) in WORD_OCCS.items():
            freq = len(occs)
            for c in word:
                CHARS[c] += freq

        CHARS_CASE_SENSITIVE = {c for c in CHARS if c.upper() != c.lower()}
        self.CHARS_SENSITIVE = CHARS_CASE_SENSITIVE
        CHARS_UPPER = {c for c in CHARS_CASE_SENSITIVE if c == c.upper()}
        CHARS_LOWER = {c for c in CHARS_CASE_SENSITIVE if c == c.lower()}
        self.CHARS_UPPER = CHARS_UPPER
        self.CHARS_LOWER = CHARS_LOWER

        charsUpperStr = "".join(sorted(CHARS_UPPER))
        charsLowerStr = "".join(sorted(CHARS_LOWER))
        self.impureRe = re.compile(r"""[\\/(^0-9.,*:<>()•«!\[\]"]""")
        self.caseRe = re.compile(f"""[{charsLowerStr}][{charsUpperStr}]""")
        self.combiRe = re.compile(r""" [bcdfghjklmnpqrstvwxz][bcdfgjk]""", re.I)

        print(f"Lower case characters: {charsLowerStr}")
        print(f"Upper case characters: {charsUpperStr}")

        charRep = "".join(sorted(CHARS, key=lambda x: -CHARS[x]))
        print(f"CHARACTERS (most frequent first):\n{charRep}")
        print("Call method charFreqs() to see the character frequencies")

    def initOcrKey(self):
        """Compile the CHAR_CLASSES spec into a dict.

        The dict maps characters into classes of characters
        that tend to be confused by OCR processes.
        """
        OCR_KEY = {}
        self.OCR_KEY = OCR_KEY

        for line in CHAR_CLASSES.strip().split("\n"):
            (clsCard, chars) = line.split(" ", 1)
            (cls, card) = clsCard
            for c in chars:
                OCR_KEY[c] = (cls, card)

    def getCompositions(self):
        """Compute all word compositions into two.

        *   `COMPOSE[False]` dict keyed initial word components,
            valued by all possible suffixes that form a word together
        *   `COMPOSE[True]` dict keyed final word components,
            valued by all possible prefixes that form a word together
        """
        C = self.C
        morfSize = C.morfSize
        WORD_OCCS = self.WORD_OCCS
        COMPOSE = {False: {}, True: {}}
        self.COMPOSE = COMPOSE

        for word in WORD_OCCS:
            lw = len(word)
            p = min((morfSize, lw))
            for i in range(1, p + 1):
                morfPre = word[0:i]
                mainPre = word[i:]
                morfPost = word[lw - i : lw]
                mainPost = word[0 : lw - i]

                COMPOSE[False].setdefault(morfPre, set()).add(mainPre)
                COMPOSE[True].setdefault(morfPost, set()).add(mainPost)

        for kind in (True, False):
            label = "suffix" if kind else "prefix"
            print(f"{len(COMPOSE[kind])} distinct {label}es")

    def clearQuality(self):
        """Initializes or clears the store of quality measurements of word splits.

        `QUALITY` is

        *   first keyed by `False` (quality of *morfs*) or
            `True` (quality of *mains*);
        *   then by `False` (quality of items at the start of a word) or
            `True` (quality of items at the end of a word);
        *   then by pairs of (pre, post) which divide words in two parts;
        *   and the eventual value is an integer or float
            that acts as the measure of the quality of that item.
        """
        if not hasattr(self, "QUALITY"):
            QUALITY = {False: {False: {}, True: {}}, True: {False: {}, True: {}}}
            self.QUALITY = QUALITY
        else:
            QUALITY = self.QUALITY
            for what in (False, True):
                for where in (False, True):
                    QUALITY[what][where].clear()

    def getFills(self, string, fill, what, where):
        """Get the ways that a string can be filled up to a word.

        *   string: a morf or a main for which we want to compute something
        *   fill: a morf or a main that we want to exclude from the computation
        *   what: whether `string` is a morf (True) or a main (False)
        *   where: whether `string` ends a word (True) or starts it (False)
        """

        C = self.C
        morfSize = C.morfSize
        COMPOSE = self.COMPOSE
        compose = COMPOSE[where]
        if string not in compose:
            return set()

        fills = compose[string]
        if what:
            # the fills are mains, and we exclude the empty main
            fills = fills - {""}
        else:
            # the fills are morfs, which are restricted in length
            fills = {f for f in fills if len(f) <= morfSize}
        # note that fills is a modified copy of the original value in compose[string]
        # we can mutate fills without touching the original
        if fill is not None and fill in fills:
            fills -= {fill}
        return fills

    def getQualityRaw(self, string, fill, what, where):
        """Compute the quality of a split, without storing results.

        *   string: a morf or a main for which we want to compute something
        *   fill: a morf or a main that we want to exclude from the computation
        *   what: whether `string` is a morf (True) or a main (False)
        *   where: whether `string` ends a word (True) or starts it (False)
        """

        return sum(
            len(self.getFills(f, string, not what, not where))
            for f in self.getFills(string, None, what, where)
        )

    def getQuality(self, string, fill, what, where):
        """Lookup or compute and store the quality of a split.

        *   string: a morf or a main for which we want to compute something
        *   fill: a morf or a main that we want to exclude from the computation
        *   what: whether `string` is a morf (True) or a main (False)
        *   where: whether `string` ends a word (True) or starts it (False)
        """

        COMPOSE = self.COMPOSE
        QUALITY = self.QUALITY

        quality = QUALITY[what][where]
        item = (string, fill)
        if item in quality:
            return quality[item]

        # if string does not occur in the corpus as word part, the quality is trivially 0
        # we do not store it.

        compose = COMPOSE[where]
        if string not in compose:
            return 0

        if what and string == "":
            return 1

        # the real computation

        if what:
            q = self.getQualityRaw(string, fill, what, where)
        else:
            q = len(self.getFills(string, fill, what, where))

        quality[string] = q
        return q

    def showSplits(self, word):
        """Show the possible splits of a word together with the quality measures.
        """
        C = self.C
        morfSize = C.morfSize
        WORD_OCCS = self.WORD_OCCS

        if word not in WORD_OCCS:
            print(f"{word} not in corpus")
            return

        lw = len(word)
        p = min((lw - 1, morfSize))

        markdown = f"**`{word}`**\n\n"

        if len(word) < 2:
            markdown += "*no splits*\n\n"
        else:
            for where in (False, True):
                preLabel = "main" if where else "morf"
                postLabel = "morf" if where else "main"

                markdown += dedent(
                    f"""\
                pos | {preLabel} | {postLabel} | qual-morf | #-morfs | qual-main | #-main
                --- | ---        | ---         | ---       | ---     | ---       | ---
                """
                )

                for i in range(1, p + 1):
                    split = lw - i if where else i
                    pre = word[0:split]
                    post = word[split:]
                    morf = post if where else pre
                    main = pre if where else post
                    n = {}
                    qual = {}
                    for (string, fill, what, thisWhere) in (
                        (main, morf, False, not where),
                        (morf, main, True, where),
                    ):
                        n[not what] = len(self.getFills(string, fill, what, thisWhere))
                        qual[what] = self.getQuality(string, fill, what, thisWhere)
                    markdown += dedent(
                        f"""\
                    {split} | {pre} | {post} | {qual[True]} | {n[True]} | {qual[False]} | {n[False]}
                    """
                    )
                markdown += "\n"

        markdown += "\n---\n"
        dm(markdown)

    def showExamples(self, examples):
        self.clearQuality()
        for word in examples:
            self.showSplits(word)

    def getGramContexts(self):
        """We harvest the 2 and 3 letter grams with their context.

        A k-context of a gram are the k-letters preceding it plus the k-letters
        following it. At the end of words we take the context characters from
        the punc feature of the word and if that is not enough, from the next word.
        At the start of a word, we take the context characters from the punc feature
        of the previous word, and if that is not enough, from the previous word itself.
        If we run out of letters, we insert spaces.
        """
        volume = self.volume
        postDir = self.postDir
        TF = self.TF

        k = 2

        GRAM_CONTEXT_PRE = {}
        GRAM_CONTEXT_POST = {}
        self.GRAM_CONTEXT_PRE = GRAM_CONTEXT_PRE
        self.GRAM_CONTEXT_POST = GRAM_CONTEXT_POST

        F = TF.api.F
        maxSlot = F.otype.maxSlot

        filePath = f"{postDir}/volume.txt"
        with open(filePath, "w") as fh:
            for w in range(1, maxSlot):
                punc = F.punc.v(w)
                nl = "\n" if "." in punc else ""
                fh.write(f"{F.letters.v(w)}{punc}{nl}")

        for n in NS:
            print(
                f"Getting {n}-gram-{k}-contexts for {maxSlot} words in volume {volume}"
            )
            theseContextsPre = collections.defaultdict(collections.Counter)
            theseContextsPost = collections.defaultdict(collections.Counter)
            flex = k + n
            for w in range(1, maxSlot + 1):
                prevPunc = "" if w == 1 else F.punc.v(w - 1)
                prevWord = "" if w == 1 else F.letters.v(w - 1)
                word = F.letters.v(w)
                postPunc = F.punc.v(w)
                postWord = "" if w == maxSlot else F.letters.v(w + 1)
                before = (" " * flex) + prevWord + prevPunc
                after = postPunc + postWord + (" " * flex)
                wordPlus = before + word + after
                startWord = len(before)
                for i in range(-1, len(word) - n + 2):
                    start = startWord + i
                    end = start + n - 1
                    gram = wordPlus[start : end + 1]
                    pre = wordPlus[start - k : start]
                    post = wordPlus[end + 1 : end + k + 1]
                    theseContextsPre[gram][pre] += 1
                    theseContextsPost[gram][post] += 1

            GRAM_CONTEXT_PRE[n] = theseContextsPre
            GRAM_CONTEXT_POST[n] = theseContextsPost

            for (kind, theseContexts) in (
                ("pre", theseContextsPre),
                ("post", theseContextsPost),
            ):
                filePath = f"{postDir}/context-{k}-{kind}-{n}-grams.tsv"
                with open(filePath, "w") as fh:
                    gram = "gram"[0:n]
                    context = "c" * k
                    heads = (
                        f"«{context}├{gram}┤"
                        if kind == "pre"
                        else f"├{gram}┤{context}»"
                    )
                    fh.write(f"{heads}\tfreqContext\tfreqGram\n")
                    for (gram, contexts) in sorted(
                        theseContexts.items(), key=lambda x: (-sum(x[1].values()), x[0])
                    ):
                        freqGram = sum(contexts.values())
                        for (context, freq) in sorted(
                            contexts.items(), key=lambda x: (-x[1], x[0])
                        ):
                            columns = (
                                f"«{context}├{gram}┤"
                                if kind == "pre"
                                else f"├{gram}┤{context}»"
                            )
                            fh.write(f"{columns}\t{freq}\t{freqGram}\n")

    def getGrams(self):
        """
        We walk through the corpus and harvest the 2- and 3- lettergrams.
        For each gram we store information about the words they occur in
        and how often they occur overall.
        We also store the immediate contexts of the grams,
        and how often each context is witnessed.

        We also build an index where we can find for each word
        the grams it contains.

        More precisely:

        When walking through the corpus, we only do the n-gram
        inventory for the distinct words.

        We also make an index of the words with respect to their occurrences
        in WORD_OCC.
        Where needed, we can easily lookup the occurrences (or frequency)
        of a given word from WORD_OCC.

        So the following steps are done per distinct word, irrespective of how
        many occurrences that word has.

        *   `GRAM[n]["gram"]` gives per n-gram a list
            of words that contain it. If a word
            contains a gram multiple times, then the list
            will contain that word that many times.
        *   `GRAM_INDEX["word"][n]` gives per word a dict
            keyed by `n` and valued with the *list* of n-grams in that word.
            So again, the multiplicity of grams in a word
            is taken into account.

        We surround each word by a space first,
        in order to be sensitive to word boundaries.
        These spaces will be included in the 2,3-grams.
        However, we do not count the space as a character,
        so we will have 2-grams like ` ab` and `ab `
        and we will have 3-grams like ` abc` and `abc `.

        While we are composing the 2,3-grams,
        we make an inventory of the single characters and their frequencies.

        For convenience, we produce a tsv file of the words,
        where we have a line for each occurrence
        with the page number and line number and word.
        This is helpful for manual lookup of words.
        """
        volume = self.volume
        postDir = self.postDir
        WORD_OCCS = self.WORD_OCCS
        TF = self.TF

        GRAM = {n: collections.defaultdict(list) for n in NS}
        self.GRAM = GRAM

        GRAM_INDEX = collections.defaultdict(lambda: {n: [] for n in NS})
        self.GRAM_INDEX = GRAM_INDEX

        GRAM_INSENSITIVE = collections.Counter()

        LEGAL_COMBIS = {
            x: {2: collections.defaultdict(dict), 3: collections.defaultdict(dict)}
            for x in (False, True)
        }
        self.LEGAL_COMBIS = LEGAL_COMBIS

        LEGAL_GRAMS = {x: {n: set() for n in NS} for x in (False, True)}
        self.LEGAL_GRAMS = LEGAL_GRAMS
        ILLEGAL_GRAMS = {x: {n: set() for n in NS} for x in (False, True)}
        self.ILLEGAL_GRAMS = ILLEGAL_GRAMS
        ALLOWED_GRAMS = {n: set() for n in NS}
        self.ALLOWED_GRAMS = ALLOWED_GRAMS

        F = TF.api.F
        T = TF.api.T
        allWords = F.otype.s("word")

        print(f"Getting 2,3-grams for {len(allWords)} words in volume {volume}")

        filePath = f"{postDir}/words.tsv"
        with open(filePath, "w") as fh:
            fh.write("page\tline\tword\n")
            for w in allWords:
                word = F.letters.v(w)

                (volume, page, line) = T.sectionFromNode(w)
                fh.write(f"{page}\t{line}\t{word}\n")
        print(f"All words written to {unexpanduser(filePath)}")

        for word in WORD_OCCS:
            end = len(word) - 1
            for (i, c) in enumerate(word):
                for n in NS:
                    start = i - n + 1
                    if start < 0:
                        if i == end and n == 2:
                            # if the word has length 1
                            # we add it to its 2-grams
                            gram = f"├{word}┤"
                        else:
                            continue
                    else:
                        prefix = "├" if start == 0 else ""
                        suffix = "┤" if i == end else ""
                        gram = prefix + word[start : i + 1] + suffix
                    GRAM[n][gram].append(word)
                    GRAM_INDEX[word][n].append(gram)
                    GRAM_INSENSITIVE[gram.lower()] += 1

        for (n, grams) in GRAM.items():
            print(f"{len(grams)} distinct {n}-grams")

    def charFreqs(self):
        """Show the frequencies of each character that occurs in the corpus."""

        if not hasattr(self, "CHARS"):
            self.getCharacters()

        CHARS = self.CHARS
        for (c, freq) in sorted(CHARS.items(), key=lambda x: (-x[1], x[0])):
            print(f"{c} {freq:>7}")

    def occFreq(self, n, gram):
        """Get the frequency of an n-gram in the corpus.

        All distinct words in which the n-gram occurs are looked up,
        and their frequencies are summed up.

        If an n-gram occurs more than once in a word, that word
        will be encountered that many times, so the frequency
        of such a word is effectively multiplied by the number of times
        the gram occurs in that word.

        Parameters
        ----------
        n: integer
            The cardinality of the grams: 2 or 3
        gram: string
            The n-gram itself, as string

        Returns
        -------
        int
            The frequency of the n-gram in the corpus
        """
        GRAM = self.GRAM
        WORD_OCCS = self.WORD_OCCS

        words = GRAM[n][gram]
        return sum(len(WORD_OCCS[word]) for word in words)

    def distFreq(self, n, kind=None):
        """Show frequency distribution of n-grams.

        Parameters
        ----------
        n: integer
            The cardinality of the grams: 2 or 3
        kind: boolean, optional None
            If None: takes all grams into account
            If False: only grams at the beginning of words
            If True: only grams at the end of words
        """
        GRAM = self.GRAM
        postDir = self.postDir

        grams = GRAM[n]
        itemLabel = f"{n}-grams{kindRep(kind)}"
        amountLabel = "word freq"
        distribution = collections.Counter()

        fileName = f"{n}-gram{kindRep(kind)}-info.tsv"
        filePath = f"{postDir}/{fileName}"
        with open(filePath, "w") as fh:
            fh.write("gram\t#words\t#occurrences\texample1\texample2\texample3\n")
            k = 0
            for (gram, words) in sorted(
                grams.items(), key=lambda x: -self.occFreq(n, x[0])
            ):
                if kind is False and gram[0] != "├" or kind is True and gram[-1] != "┤":
                    continue
                k += 1
                examples = list(words)[0:3]
                exampleRep = "\t".join(examples)
                nWords = len(words)
                nOccs = self.occFreq(n, gram)
                distribution[nOccs] += 1
                fh.write(f"{gram}\t{nWords}\t{nOccs}\t{exampleRep}\n")
        print(f"All {n}-grams written to {unexpanduser(filePath)}")

        print(f"\n{k} {itemLabel}{kindRep(kind)}\n")
        showDistributionFreq(distribution, itemLabel, amountLabel)

    def getCombis(self, kind, n, deliver=False):
        """Get n-grams that start or end with consonant combinations.

        Parameters
        ----------
        n: integer
            The cardinality of the grams: 2 or 3
        kind: boolean, optional None
            If False: only grams at the beginning of words
            If True: only grams at the end of words
        deliver: boolean, optional False
            If True, suppress console output and return
            the dict of combinations.

        Returns
        -------
        None or dict
            If deliver, a dict keyed with all n-grams that are a consonant combination
            at the appropriate side of the word, and valued with
            the tuple of main part and other parts of the combination, lowercased.
        """
        GRAM = self.GRAM
        ILLEGAL_GRAMS = self.ILLEGAL_GRAMS
        theseIllegalGrams = ILLEGAL_GRAMS[kind][2]
        combis = collections.defaultdict(collections.Counter)
        allCombis = dict()

        boundary = -1 if kind else 0
        otherBoundary = 0 if kind else -1
        boundaryChar = "┤" if kind else "├"
        otherBoundaryChar = "├" if kind else "┤"
        method = (
            (lambda x: x[0:-1].replace(otherBoundaryChar, ""))
            if kind
            else (lambda x: x[1:].replace(boundaryChar, ""))
        )

        if n == 2:
            for gram in GRAM[n]:
                if not isTrueBi(gram):
                    continue
                if gram[boundary] != boundaryChar:
                    continue
                bareGram = method(gram).lower()
                if not CONSONANT_RE.match(bareGram):
                    continue
                freq = self.occFreq(n, gram)
                main = bareGram[boundary]
                other = bareGram[otherBoundary]
                combis[main][other] += freq
                allCombis[gram] = (main, other)
        elif n == 3:
            for gram in GRAM[n]:
                if gram[boundary] != boundaryChar:
                    continue
                bareGram = method(gram)
                bigram = bareGram[1:] if kind else bareGram[0:-1]
                bigram = f"{bigram}┤" if kind else f"├{bigram}"
                bigramPlus = f"├{bigram}" if kind else f"{bigram}┤"
                if bigram in theseIllegalGrams or bigramPlus in theseIllegalGrams:
                    continue
                bareGram = bareGram.lower()
                if not bareGram[otherBoundary].isalpha():
                    continue
                main = bareGram[1:] if kind else bareGram[0:-1]
                if not CONSONANT_RE.match(main):
                    continue
                other = bareGram[otherBoundary]
                freq = self.occFreq(n, gram)
                combis[main][other] += freq
                allCombis[gram] = (main, other)

        if deliver:
            return allCombis

        print(f"All {n}{kindRep(kind)}-combis\n")
        for (main, others) in sorted(
            combis.items(), key=lambda x: (-sum(x[1].values()), x[0])
        ):
            lines = [[], []]
            mainRep = f"+{main}" if kind else f"{main}+"
            for (other, freq) in [(mainRep, sum(others.values()))] + sorted(
                others.items(), key=lambda x: (-x[1], x[0])
            ):
                freqRep = str(freq)
                width = max((len(freqRep), len(mainRep)))
                lines[0].append(f"{freqRep:<{width}}")
                lines[1].append(f"{other:<{width}}")
            for line in lines:
                print("|".join(line))
            print("")

    def legalizeCombis(self, kind, n, illegalSpec):
        """Weed out illegal consonant combinations from n-grams.

        Parameters
        ----------
        n: integer
            The cardinality of the grams: 2 or 3
        kind: boolean, optional None
            If False: only grams at the beginning of words
            If True: only grams at the end of words
        legalSpec: string
            Specification of illegal combinations.
            A series of lines of the form

            ```
            main=+others
            ```

            or

            ```
            main=-others
            ```

            Main is the main part of a combination, others is the concatenation
            of all possible other parts of the combination.

            For n-grams
            *   at the start: other is the last letter of the n-gram.
            *   at the end: other is the first letter of the n-gram.

            Main is the rest of the n-gram.

            The others part is preceded by
            *   `+` : all these combinations are legal.
            *   `-` : all these combinations are illegal.

            If the parts after the `+` or `-` is empty, it means
            all combinations with the main part are illegal or legal respectively.
        """
        GRAM = self.GRAM
        LEGAL_COMBIS = self.LEGAL_COMBIS
        LEGAL_GRAMS = self.LEGAL_GRAMS
        ILLEGAL_GRAMS = self.ILLEGAL_GRAMS

        theseLegalCombis = LEGAL_COMBIS[kind][n]
        theseLegalGrams = LEGAL_GRAMS[kind][n]
        theseIllegalGrams = ILLEGAL_GRAMS[kind][n]

        theseLegalCombis.clear()
        theseLegalGrams.clear()
        theseIllegalGrams.clear()

        for line in illegalSpec.strip().split("\n"):
            (main, others) = line.split(None, 1)
            (isLegal, others) = (others[0], others[1:])
            isLegal = isLegal == "+"
            theseLegalCombis[main]["legal"] = isLegal
            theseLegalCombis[main].setdefault("others", set())
            for other in others:
                theseLegalCombis[main]["others"].add(other)

        print("Legality declaration")
        for (main, data) in sorted(theseLegalCombis.items()):
            isLegal = data["legal"]
            legalRep = "+" if isLegal else "-"
            xLegalRep = "-" if isLegal else "+"
            others = data["others"]
            itemsRep = (
                " ".join(f"{legalRep}{main}{other}" for other in sorted(others))
                if others
                else f"{xLegalRep}{main}*"
            )
            print(itemsRep)

        allCombis = self.getCombis(kind, n, deliver=True)
        for (gram, (main, other)) in allCombis.items():
            data = theseLegalCombis.get(main, None)
            if data is None:
                print(
                    dedent(
                        f"""\
                Cannot find legality information for {n}-gram |{gram}|:
                No entry for main part |{main}|"""
                    )
                )
                continue
            isLegal = data["legal"]
            inOthers = other in data["others"]
            isLegal = isLegal and inOthers or not isLegal and not inOthers
            if isLegal:
                theseLegalGrams.add(gram)
            else:
                theseIllegalGrams.add(gram)

        kindCombis = sum(
            1
            for x in GRAM[n]
            if isTrueBi(x)
            and (kind and x.endswith("┤") or not kind and x.startswith("├"))
        )
        print(
            dedent(
                f"""
        Total number of {n}-grams{kindRep(kind)}:        {kindCombis:>5}
        Total number of consonant combis among them: {len(allCombis):>5}
        Of which are   legal:                        {len(theseLegalGrams):>5}
                 and illegal:                        {len(theseIllegalGrams):>5}
        """
            )
        )

    def getLegalGrams(self, LIMIT):
        impureRe = self.impureRe
        caseRe = self.caseRe
        postDir = self.postDir
        GRAM = self.GRAM
        LEGAL_GRAMS = self.LEGAL_GRAMS
        ILLEGAL_GRAMS = self.ILLEGAL_GRAMS
        ALLOWED_GRAMS = self.ALLOWED_GRAMS

        for (n, grams) in GRAM.items():
            limit = LIMIT[n]
            theseAllowed = ALLOWED_GRAMS[n]
            theseAllowed.clear()
            allowed = LEGAL_GRAMS[False][n] | LEGAL_GRAMS[True][n]
            unAllowed = ILLEGAL_GRAMS[False][n] | ILLEGAL_GRAMS[True][n]

            for gram in grams:
                if impureRe.search(gram) or caseRe.search(gram):
                    continue

                if gram in allowed:
                    theseAllowed.add(gram)
                    continue
                if gram in unAllowed:
                    continue

                freq = self.occFreq(n, gram)
                if freq >= limit:
                    theseAllowed.add(gram)

        for (n, grams) in ALLOWED_GRAMS.items():
            distribution = collections.Counter()

            filePath = f"{postDir}/legal-{n}-grams.tsv"
            with open(filePath, "w") as fh:
                fh.write("gram\tfrequency\n")
                for gram in sorted(grams, key=lambda x: -self.occFreq(n, x)):
                    freq = self.occFreq(n, gram)
                    distribution[freq] += 1
                    fh.write(f"{gram}\t{freq}\n")
            print(f"All legal {n}-grams written to {unexpanduser(filePath)}")

            print(f"\n{len(grams)} legal {n}-grams\n")
            showDistributionFreq(distribution, f"legal {n}-gram", "occurrences")

    def getLegalWords(self):
        GRAM_INDEX = self.GRAM_INDEX
        ALLOWED_GRAMS = self.ALLOWED_GRAMS
        postDir = self.postDir

        LEGAL_WORD = {}
        self.LEGAL_WORD = LEGAL_WORD

        for (word, info) in GRAM_INDEX.items():
            legal = 0
            divider = 0
            for (n, grams) in info.items():
                if len(grams) == 0:
                    continue
                divider += 1
                legal += int(
                    round(
                        100
                        * sum(1 for gram in grams if gram in ALLOWED_GRAMS[n])
                        / len(grams)
                    )
                )
            legal = int(round(legal / divider)) if divider else 0
            LEGAL_WORD[word] = legal

        distribution = collections.Counter()

        filePath = f"{postDir}/legal-words.tsv"
        with open(filePath, "w") as fh:
            fh.write("word\tlegality\n")
            for (word, legality) in sorted(
                LEGAL_WORD.items(), key=lambda x: (-x[1], x[0])
            ):
                fh.write(f"{word}\t{legality}\n")
                distribution[legality] += 1
        print(f"Legality of words written to {unexpanduser(filePath)}")

        print(f"{len(GRAM_INDEX)} words with legality distributed as:")
        showDistributionFreq(distribution, "word", "legality")

    def getOcrKey(self, word):
        """Get the OCR key for a string.

        Parameters
        ----------
        word: string
            The input string that we need the OCR key of

        Returns
        -------
        string
            The concatenation of the OCR-key mapping
            of each character in the input string.
        """
        OCR_KEY = self.OCR_KEY

        clses = []
        for c in word:
            (cls, card) = OCR_KEY.get(c, (c, 1))
            if clses and clses[-1][0] == cls:
                clses[-1][1] += card
            else:
                clses.append([cls, card])
        return "".join(f"{cls}{card}" for (cls, card) in clses)

    def makeOcrIndex(self):
        WORD_OCCS = self.WORD_OCCS
        LEGAL_WORD = self.LEGAL_WORD
        postDir = self.postDir

        WORD_OCR = {x: collections.defaultdict(list) for x in (False, True)}
        self.WORD_OCR = WORD_OCR

        ocrFreq = {x: collections.Counter() for x in (False, True)}

        for (word, occs) in WORD_OCCS.items():
            ocrKey = self.getOcrKey(word)
            legality = LEGAL_WORD[word]
            isLegal = legality >= 100
            WORD_OCR[isLegal][ocrKey].append(word)
            ocrFreq[isLegal][ocrKey] += len(occs)

        for isLegal in (False, True):
            legalRep = "legal" if isLegal else "illegal"
            theseWordOcr = WORD_OCR[isLegal]
            theseOcrFreq = ocrFreq[isLegal]

            distribution = collections.Counter()

            filePath = f"{postDir}/ocrkeys-{legalRep}.tsv"
            with open(filePath, "w") as fh:
                fh.write("#words\tocr-kkey\tword\tlegality\n")
                for (okey, words) in sorted(
                    theseWordOcr.items(), key=lambda x: (-len(x[1]), x[0])
                ):
                    nw = len(words)
                    distribution[theseOcrFreq[okey]] += 1
                    for word in sorted(words, key=lambda x: (-LEGAL_WORD[x], x)):
                        legality = LEGAL_WORD[word]
                        fh.write(f"{nw}\t{okey}\t{word}\t{legality}\n")
            print(f"OCR-keys written to {unexpanduser(filePath)}")

            print(
                f"Words with {legalRep} forms clustered "
                f"into {len(theseWordOcr)} ocr keys"
            )
            showDistributionFreq(distribution, "ocr-keys", f"{legalRep} occurrences")

    def makeOcrMatrix(self):
        WORD_OCR = self.WORD_OCR

        MATRIX = collections.defaultdict(dict)
        self.MATRIX = MATRIX

        ocrLegal = sorted(WORD_OCR[True])
        ocrIllegal = sorted(WORD_OCR[False])
        nOcrLegal = len(ocrLegal)
        nOcrIllegal = len(ocrIllegal)
        totalComparisons = nOcrLegal * nOcrIllegal
        block = int(round(totalComparisons / 100))
        comparisons = 0
        entries = 0
        k = 0
        print(
            f"Creating a distance matrix between {nOcrIllegal} illegal "
            f"and {nOcrLegal} legal ocr-keys"
        )
        print(f"Going to make {totalComparisons} comparisons")

        threshold = 0.8

        for wordI in ocrIllegal:
            for wordL in ocrLegal:
                k += 1
                comparisons += 1
                if k == block:
                    perc = int(round(100 * comparisons / totalComparisons))
                    sys.stdout.write(f"\r\t{perc:>3}% {entries:>7} entries")
                    k = 0
                sim = ratio(wordI, wordL)
                if sim >= threshold:
                    MATRIX[wordI][wordL] = sim
                    entries += 1
        perc = int(round(100 * comparisons / totalComparisons))
        sys.stdout.write(f"\r\t{perc:>3}% {entries:>7} entries")
        print("")

    def correctOcr(self):
        postDir = self.postDir
        MATRIX = self.MATRIX
        WORD_OCR = self.WORD_OCR
        ocrIllegal = WORD_OCR[False]
        ocrLegal = WORD_OCR[True]

        closeThreshold = 0.8
        gapThreshold = 0.1

        CORRECTED = {}
        self.CORRECTED = CORRECTED
        legend = {
            -3: "no legal occurrences at all",
            -2: "no legal close neighbours",
            -1: "close legal neighbours too similar",
            0: "closest legal neighbour chosen",
            1: "one close legal neighbour",
        }
        keyThreshold = 0.9
        correctionLog = {status: [] for status in legend}

        candidates = 0

        for (ocrKey, illegals) in sorted(
            ocrIllegal.items(), key=lambda x: (-len(x[0]), -len(x[1]))
        ):
            candidates += len(illegals)

            thisMatrix = MATRIX.get(ocrKey, None)
            ocrKeysLegal = (
                []
                if thisMatrix is None
                else [okey for (okey, sim) in thisMatrix.items() if sim >= keyThreshold]
            )
            legals = list(chain.from_iterable(ocrLegal[okey] for okey in ocrKeysLegal))
            if len(legals) == 0:
                for illegal in illegals:
                    correctionLog[-3].append(illegal)
                continue

            for illegal in illegals:
                neighbours = []

                for legal in legals:
                    sim = ratio(illegal, legal)
                    if sim < closeThreshold:
                        continue
                    neighbours.append((legal, sim))

                if len(neighbours) == 0:
                    correctionLog[-2].append(illegal)
                    continue

                closest = neighbours[0]

                if len(neighbours) > 1:
                    neighbours = sorted(neighbours, key=lambda x: -x[1])
                    if closest[1] - neighbours[1][1] < gapThreshold:
                        correctionLog[-1].append(illegal)
                        continue
                    correctionLog[0].append(illegal)
                    CORRECTED[illegal] = closest
                    continue

                correctionLog[1].append(illegal)
                CORRECTED[illegal] = closest

        print(f"{candidates} correction candidates")
        print(f"Made {len(CORRECTED)} corrections")
        distribution = {status: len(items) for (status, items) in correctionLog.items()}
        showDistribution(distribution, "corrections", "status", legend=legend)

        filePath = f"{postDir}/correctionlog.tsv"
        with open(filePath, "w") as fh:
            fh.write("illegal\tlegal\tsimilarity\tcode\texplanation\n")
            for (code, illegals) in sorted(
                correctionLog.items(), key=lambda x: (-x[0], -len(x[1]))
            ):
                for illegal in sorted(illegals, key=lambda x: (-len(x), x)):
                    (legal, sim) = CORRECTED.get(illegal, ("", 0))
                    fh.write(f"{illegal}\t{legal}\t{sim:.1f}\t{code}\t{legend[code]}\n")
        print(f"correctionlog written to {unexpanduser(filePath)}")
