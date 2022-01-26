import os
import collections
from math import log2
import numpy as np
from tf.app import use


REPORT_DIR = os.path.expanduser(
    "~/github/clariah/wp6-daghregisters/postocr/daghregister/004"
)


class Corpus:
    def __init__(self, plt):
        A = use("clariah/wp6-daghregisters:clone", checkout="clone")
        F = A.api.F
        words = [F.letters.v(w) for w in range(1, F.otype.maxSlot + 1)]
        self.words = words
        self.plt = plt

    def getFreqs(self):
        words = self.words

        freqs = collections.Counter()
        for word in words:
            freqs[word] += 1

        self.freqs = freqs

    def showFreqs(self):
        plt = self.plt

        if not hasattr(self, "freqs"):
            self.getFreqs()
        freqs = self.freqs

        values = np.fromiter((log2(f) for f in freqs.values()), float)
        (frequency, bins) = np.histogram(values, bins=100)
        fig, ax = plt.subplots()
        ax.hist(values, bins=100)
        # ax.set(xticks=np.arange(-10, 20))
        plt.gca().set(title="Word frequencies", ylabel="Frequency")
        plt.show()

        nHapax = sum(1 for f in freqs.values() if f == 1)
        print(f"{len(freqs)} words of which {nHapax} are hapax")

    def printFreqs(self, fileName):
        self.getFreqs()
        freqs = self.freqs

        with open(f"{REPORT_DIR}/{fileName}.tsv", "w") as fh:
            for (word, freq) in sorted(freqs.items(), key=lambda x: (-x[1], x[0])):
                fh.write(f"{word}\t{freq}\n")

    def splitup(self):
        self.getFreqs()
        freqs = self.freqs
        words = self.words

        wordSplits = collections.defaultdict(dict)

        allWords = sorted({word for word in words if not word.isdigit()})
        print(f"{len(allWords)} distinct words")

        for word in allWords:
            wn = len(word)
            if wn < 4:
                continue
            maxQ = None
            (word1Best, word2Best) = (None, None)
            for s in range(2, len(word) - 1):
                word1 = word[0:s]
                word2 = word[s:]

                word1C = freqs[word1]
                word2C = freqs[word2]
                if word1C < 3 or word2C < 3:
                    continue
                q = (word1C - 1) * (word2C - 1)
                if q:
                    if maxQ is None or maxQ < q:
                        maxQ = q
                        (word1Best, word2Best) = (word1, word2)
            if maxQ:
                wordSplits[word] = (word1Best, word2Best)

        print(f"{len(wordSplits)} word split candidates")

        newWords = []

        for (i, word) in enumerate(words):
            if word.isdigit():
                continue

            newWords.extend(wordSplits.get(word, [word]))

        self.words = newWords
        self.getFreqs()
