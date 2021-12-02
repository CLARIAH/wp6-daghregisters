import os
import re
import collections
from bisect import bisect
from textwrap import dedent

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


def showDistribution(data, itemLabel, amountLabel, maxBuckets=50, maxAmounts=80):
    """Show a frequency distribution of data with exponentially growing bins.

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

    showDistribution(data, "items", "freq")

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


NS = (2, 3)


class PostOcr:
    def __init__(self, volume):
        self.volume = volume
        self.good = self.config()
        self.loadTf()
        self.getGrams()

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

    def getGrams(self):
        """
        We walk through the corpus and harvest the 2- and 3- lettergrams.
        For each gram we store information about the forms they occur in
        and how often they occur overall.

        We also build an index where we can find for each word form
        the grams it contains.

        More precisely:

        When walking through the corpus, we only do the n-gram
        inventory for the distinct word forms.

        We also make an index of the word forms with respect to their occurrences
        in WORD_OCC.
        Where needed, we can easily lookup the occurrences (or frequency)
        of a given word form from WORD_OCC.

        So the following steps are done per distinct word form, irrespective of how
        many occurrences that word form has.

        *   `GRAM[n]["gram"]` gives per n-gram a list
            of word forms that contain it. If a word form
            contains a gram multiple times, then the list
            will contain that word form that many times.
        *   `GRAM_INDEX["form"][n]` gives per form a dict
            keyed by `n` and valued with the *list* of n-grams in that form.
            So again, the multiplicity of grams in a word
            is taken into account.

        We surround each word by a space first,
        in order to be sensitive to word boundaries.
        These spaces will be included in the 2,3-gtams.
        However, we do not count the space as a character,
        so we will have 2-grams like ` ab` and `ab `
        and we will have 3-grams like ` abc` and `abc `.

        While we are composing the 2,3-grams,
        we make an inventory of the single characters and their frequencies.

        For convenience, we produce a tsv file of the forms,
        where we have a line for each occurrence
        with the page number and line number and word form.
        This is helpful for manual lookup of forms.
        """
        volume = self.volume
        postDir = self.postDir
        TF = self.TF

        WORD_OCCS = collections.defaultdict(list)
        self.WORD_OCCS = WORD_OCCS

        GRAM = {n: collections.defaultdict(list) for n in NS}
        self.GRAM = GRAM

        GRAM_INDEX = collections.defaultdict(lambda: {n: [] for n in NS})
        self.GRAM_INDEX = GRAM_INDEX

        GRAM_INSENSITIVE = collections.Counter()

        CHARS = collections.Counter()
        self.CHARS = CHARS

        LEGAL_COMBIS = {
            False: {2: collections.defaultdict(dict), 3: collections.defaultdict(dict)},
            True: {2: collections.defaultdict(dict), 3: collections.defaultdict(dict)},
        }
        self.LEGAL_COMBIS = LEGAL_COMBIS

        LEGAL_GRAMS = {False: {2: set(), 3: set()}, True: {2: set(), 3: set()}}
        self.LEGAL_GRAMS = LEGAL_GRAMS
        ILLEGAL_GRAMS = {False: {2: set(), 3: set()}, True: {2: set(), 3: set()}}
        self.ILLEGAL_GRAMS = ILLEGAL_GRAMS
        ALLOWED_GRAMS = {2: set(), 3: set()}
        self.ALLOWED_GRAMS = ALLOWED_GRAMS

        F = TF.api.F
        T = TF.api.T
        allWords = F.otype.s("word")

        print(f"Getting 2,3-grams for {len(allWords)} words in volume {volume}")

        formFile = f"{postDir}/forms.tsv"

        with open(f"{formFile}", "w") as fh:
            for w in allWords:
                letters = F.letters.v(w)

                for c in letters:
                    CHARS[c] += 1

                (volume, page, line) = T.sectionFromNode(w)
                fh.write(f"{page}\t{line}\t{letters}\n")

                if letters in WORD_OCCS:
                    # we have seen this form already
                    WORD_OCCS[letters].append(w)
                    continue

                WORD_OCCS[letters].append(w)

                end = len(letters) - 1
                for (i, c) in enumerate(letters):
                    for n in NS:
                        start = i - n + 1
                        if start >= 0:
                            prefix = " " if start == 0 else ""
                            suffix = " " if i == end else ""
                            gram = prefix + letters[start : i + 1] + suffix
                            GRAM[n][gram].append(letters)
                            GRAM_INDEX[letters][n].append(gram)
                            GRAM_INSENSITIVE[gram.lower()] += 1

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

        print(f"{len(allWords)} words in {len(WORD_OCCS)} distinct forms")
        print(f"Word forms with page/line numbers written to {formFile}")

        for (n, grams) in GRAM.items():
            print(f"{len(grams)} distinct {n}-grams")

    def charFreqs(self):
        """Show the frequencies of each character that occurs in the corpus."""
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

        forms = GRAM[n][gram]
        return sum(len(WORD_OCCS[form]) for form in forms)

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
        fileName = f"{n}-gram-info.tsv"
        itemLabel = f"{n}-grams"
        amountLabel = "word freq"
        distribution = collections.Counter()
        with open(f"{postDir}/{fileName}", "w") as fh:
            k = 0
            for (gram, forms) in sorted(
                grams.items(), key=lambda x: -self.occFreq(n, x[0])
            ):
                if kind is False and gram[0] != " " or kind is True and gram[-1] != " ":
                    continue
                k += 1
                examples = list(forms)[0:3]
                exampleRep = "\t".join(examples)
                nForms = len(forms)
                nOccs = self.occFreq(n, gram)
                distribution[nOccs] += 1
                fh.write(f"{gram}\t{nForms}\t{nOccs}\t{exampleRep}\n")
        kindRep = (
            ""
            if kind is None
            else " word-starters only"
            if kind is False
            else " word-enders only"
        )
        print(f"\n{k} {itemLabel}{kindRep}\n")
        showDistribution(distribution, itemLabel, amountLabel)

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
        method = (lambda x: x[0:-1].lstrip()) if kind else (lambda x: x[1:].rstrip())

        if n == 2:
            for gram in GRAM[n]:
                if gram[boundary] != " ":
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
                if gram[boundary] != " ":
                    continue
                bareGram = method(gram)
                bigram = bareGram[1:] if kind else bareGram[0:-1]
                bigram = f"{bigram} " if kind else f" {bigram}"
                bigramPlus = f" {bigram}" if kind else f"{bigram} "
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

        print(f"All {n}-combis at the {'end' if kind else 'start'} of words\n")
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
        theseIlLegalGrams = ILLEGAL_GRAMS[kind][n]

        theseLegalCombis.clear()
        theseLegalGrams.clear()
        theseIlLegalGrams.clear()

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
                theseIlLegalGrams.add(gram)

        kindRep = "end" if kind else "start"
        print(
            dedent(
                f"""
        Total number of {kindRep:<5} {n}-grams:               {len(GRAM[n]):>5}
        Total number of consonant combis among them: {len(allCombis):>5}
        Of which are   legal:                        {len(theseLegalGrams):>5}
                 and illegal:                        {len(theseIlLegalGrams):>5}
        """
            )
        )

    def getLegals(self, LIMIT):
        impureRe = self.impureRe
        caseRe = self.caseRe
        postDir = self.postDir
        GRAM = self.GRAM
        LEGAL_GRAMS = self.LEGAL_GRAMS
        ILLEGAL_GRAMS = self.ILLEGAL_GRAMS
        ALLOWED_GRAMS = self.ALLOWED_GRAMS

        for n in NS:
            ALLOWED_GRAMS[n] = LEGAL_GRAMS[False][n] | LEGAL_GRAMS[True][n]

        for (n, grams) in GRAM.items():
            limit = LIMIT[n]
            allowed = ALLOWED_GRAMS[n]
            unAllowed = ILLEGAL_GRAMS[False][n] | ILLEGAL_GRAMS[True][n]

            for (gram, forms) in grams.items():
                if gram in allowed:
                    # gram is already in
                    continue
                if gram in unAllowed:
                    # do not put gram in
                    continue

                freq = self.occFreq(n, gram)
                if (
                    freq >= limit
                    and not impureRe.search(gram)
                    and not caseRe.search(gram)
                ):
                    allowed.add(gram)

        for (n, grams) in ALLOWED_GRAMS.items():
            print(f"\n{len(grams)} legal {n}-grams\n")
            with open(f"{postDir}/legal-{n}-grams.tsv", "w") as fh:
                distribution = collections.Counter()
                for gram in sorted(grams, key=lambda x: self.occFreq(n, x)):
                    freq = self.occFreq(n, gram)
                    distribution[freq] += 1
                    fh.write(f"{gram}\t{freq}\n")
                showDistribution(distribution, f"legal {n}-gram", "occurrences")

    def getLegality(self):
        GRAM_INDEX = self.GRAM_INDEX
        ALLOWED_GRAMS = self.ALLOWED_GRAMS
        postDir = self.postDir

        LEGAL_FORM = {}
        self.LEGAL_FORM = LEGAL_FORM

        for (form, info) in GRAM_INDEX.items():
            legal = 0
            for (n, grams) in info.items():
                if len(grams) == 0:
                    continue
                legal += int(
                    round(
                        100
                        * sum(1 for gram in grams if gram in ALLOWED_GRAMS[n])
                        / len(grams)
                    )
                )
            legal = int(round(legal / 2))
            LEGAL_FORM[form] = legal

        print(f"{len(GRAM_INDEX)} word forms with legality distributed as:")
        with open(f"{postDir}/legality.tsv", "w") as fh:
            distribution = collections.Counter()
            for (form, leg) in sorted(LEGAL_FORM.items(), key=lambda x: (-x[1], x[0])):
                fh.write(f"{form}\t{leg}\n")
                distribution[leg] += 1
            showDistribution(distribution, "word form", "legality")
