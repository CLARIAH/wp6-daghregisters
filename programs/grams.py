from itertools import chain
import collections
from math import log2


N = 4


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

    def getGrams(self):
        wordOccs = self.wordOccs

        GRAM = collections.defaultdict(list)
        self.GRAM = GRAM

        GRAM_INDEX = collections.defaultdict(list)
        self.GRAM_INDEX = GRAM_INDEX

        GRAM_FREQ = {}
        self.GRAM_FREQ = GRAM_FREQ

        WORD_QUALITY = {}
        self.WORD_QUALITY = WORD_QUALITY

        for word in wordOccs:
            theWord = f"├{word}┤"
            useN = int(round(N / 2)) if len(theWord) < N + 2 else N
            for i in range(len(theWord) - useN + 1):
                gram = theWord[i:i + useN]
                GRAM[gram].append(word)
                GRAM_INDEX[word].append(gram)

        print(f"{len(GRAM)} distinct {N}-grams")

        for (gram, words) in GRAM.items():
            GRAM_FREQ[gram] = log2(sum(len(wordOccs[word]) for word in words))

        for (word, occs) in wordOccs.items():
            freq = len(occs)
            WORD_QUALITY[word] = sum(GRAM_FREQ[gram] for gram in GRAM_INDEX[word]) * freq / len(word)
