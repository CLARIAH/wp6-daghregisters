import os
import collections


class WordSplit:
    def __init__(self, volume):
        self.volume = volume
        self.good = self.config()
        self.loadTf()
        self.getWords()

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

    def getCompositions(self):
        """Compute all word compositions into two.

        `COMPOSE` is

        *   first keyed by what: `False` (components are morfs) or
            `True` (components are mains)
        *   then by where: `False` (component is at the start) or
            `True` (components are at the end)
        *   then by the component itself
        *   and the value is the set of all possible ways the component
            can be completed into a word.
        """
        C = self.C
        morfSize = C.morfSize
        WORD_OCCS = self.WORD_OCCS
        COMPOSE = {
            what: {where: {} for where in (False, True)} for what in (False, True)
        }
        self.COMPOSE = COMPOSE

        for word in WORD_OCCS:
            lw = len(word)
            p = min((morfSize, lw))
            item = {what: {} for what in (False, True)}
            for i in range(1, p + 1):
                item[True][False] = word[0:i]
                item[False][False] = word[i:]
                item[True][True] = word[lw - i : lw]
                item[False][True] = word[0 : lw - i]

                for (what, wheres) in item.items():
                    for (where, string) in wheres.items():
                        COMPOSE[what][where].setdefault(string, set()).add(item[not what][not where])

        for what in (True, False):
            theWhat = "morf" if what else "main"
            for (where, data) in COMPOSE[what].items():
                theWhere = "suffix" if where else "prefix"
                print(f"{len(data)} distinct {theWhat}-{theWhere} candidates")
