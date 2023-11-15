from itertools import chain
import re
import collections
from textwrap import dedent


CONSONANT_RE = re.compile(r"""[bcdfghjklmnpqrstvwxz]{2}""")


def kindRep(kind):
    return "" if kind is None else "-start" if kind is False else "-end"


def isTrueBi(gram):
    return not (len(gram) == 3 and gram[0] == "├" and gram[-1] == "┤")


NS = (2, 3)


class Gram:
    def __init__(self, words):
        self.origWords = words
        self.words = list(chain.from_iterable((w for w in word.split("┼") if not w.startswith("⁼")) for word in words))
        words = self.words

        wordOccs = collections.defaultdict(list)
        self.wordOccs = wordOccs

        for (w, word) in enumerate(words):
            wordOccs[word].append(w)
        print(f"{len(wordOccs)} words in {len(words)} occurrences")

        chars = collections.Counter()

        for (word, occs) in wordOccs.items():
            freq = len(occs)
            for c in word:
                chars[c] += freq

        caseSensitive = {c for c in chars if c.upper() != c.lower()}
        uppers = {c for c in caseSensitive if c == c.upper()}
        lowers = {c for c in caseSensitive if c == c.lower()}

        charsUpperStr = "".join(sorted(uppers))
        charsLowerStr = "".join(sorted(lowers))
        self.impureRe = re.compile(r"""[\\/(^0-9.,*:<>()•«!\[\]"]""")
        self.caseRe = re.compile(f"""[{charsLowerStr}][{charsUpperStr}]""")

        print(f"Lower case characters: {charsLowerStr}")
        print(f"Upper case characters: {charsUpperStr}")

        charRep = "".join(sorted(chars, key=lambda x: -chars[x]))
        print(f"CHARACTERS (most frequent first):\n{charRep}")

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
        in `WORD_OCC`.
        Where needed, we can easily lookup the occurrences (or frequency)
        of a given word from `WORD_OCC`.

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

        For convenience, we produce a TSV file of the words,
        where we have a line for each occurrence
        with the page number and line number and word.
        This is helpful for manual lookup of words.
        """
        wordOccs = self.wordOccs

        GRAM = {n: collections.defaultdict(list) for n in NS}
        self.GRAM = GRAM

        GRAM_INDEX = collections.defaultdict(lambda: {n: [] for n in NS})
        self.GRAM_INDEX = GRAM_INDEX

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

        for word in wordOccs:
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

        for (n, grams) in GRAM.items():
            print(f"{len(grams)} distinct {n}-grams")

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
        wordOccs = self.wordOccs

        words = GRAM[n][gram]
        return sum(len(wordOccs[word]) for word in words)

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

    def getLegalWords(self):
        GRAM_INDEX = self.GRAM_INDEX
        ALLOWED_GRAMS = self.ALLOWED_GRAMS

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
