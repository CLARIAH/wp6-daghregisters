import os
import collections
import re

from Levenshtein import distance, ratio

from config import Config

wordRe = re.compile(r"""^(.*?)(\W*)$""")
endElemRe = re.compile(r"""^</(\S+)>$""")
elemRe = re.compile(r"""^<([^> ]+)""")
clsRe = re.compile(r'''class="([^"]*)"''')
titleRe = re.compile(r'''title="([^"]*)"''')
contentRe = re.compile(r""">([^<]*)</span>""")


PHOTO = "photo"
TABLE = "table"
PAGE = "page"
AREA = "area"
PARA = "para"
LINE = "line"
WORD = "word"
CHAR = "char"
TR = "tr"
TD = "td"

clsDef = dict(
    ocr_photo=PHOTO,
    ocr_table=TABLE,
    ocr_page=PAGE,
    ocr_carea=AREA,
    ocr_par=PARA,
    ocr_line=LINE,
    ocrx_word=WORD,
    ocrx_cinfo=CHAR,
)

IGNORE_ELEM = {"html", "head", "title", "meta", "body"}
CLSLESS_ELEM = {"table", "tr", "td"}


class Hocr:
    def __init__(self):
        self.config()

    def config(self):
        C = Config()
        self.C = C
        self.source = f"{C.local}/{C.name}_chocr.html"
        self.simpleSource = f"{C.local}/{C.name}_chocr.tsv"
        self.dest = f"{C.local}/{C.name}_words.tsv"

    def simplify(self):
        source = self.source
        simpleSource = self.simpleSource
        print("Simplifying HOCR source")

        unmatchedLines = []
        nest = []

        with open(source) as fh, open(simpleSource, "w") as dh:
            for (i, line) in enumerate(fh):
                error = ""
                line = line.strip()
                if line == "":
                    continue

                match = endElemRe.match(line)
                if match:
                    elem = match.group(1)
                    if elem in IGNORE_ELEM:
                        continue
                    if len(nest) == 0:
                        print(f"Line {i + 1}: empty stack:")
                        print(f"{line}\n")
                        break
                    container = nest.pop()
                    dh.write(f"∪{container}\n")
                    continue

                outFields = []
                afterLine = ""
                match = elemRe.match(line)
                if match:
                    elem = match.group(1)
                    if elem[0] in {"?", "!"} or elem in IGNORE_ELEM:
                        continue
                    match = clsRe.search(line)
                    container = None
                    if match:
                        cls = match.group(1)
                        container = clsDef[cls]
                    else:
                        if elem in CLSLESS_ELEM:
                            container = elem
                    if container is None:
                        error += f" no elem class in {elem}"
                    else:
                        if container != CHAR:
                            outFields.append(f"∩{container}")
                            nest.append(container)
                        if line.endswith("/>"):
                            afterLine = f"∪{container}\n"
                            nest.pop()
                else:
                    error += " no elem"

                match = contentRe.search(line)
                if match:
                    content = match.group(1)
                    outFields.append(content)

                match = titleRe.search(line)
                if match:
                    title = match.group(1)
                    comps = title.split(";")
                    for comp in comps:
                        comp = comp.strip()
                        (key, value) = comp.split(" ", 1)
                        key = key.removeprefix("x_")
                        if key.startswith("bbox"):
                            key = "box"
                        outFields.append(f"{key}={value}")
                else:
                    if elem not in CLSLESS_ELEM:
                        error += " no title "

                if error:
                    unmatchedLines.append((i, error, line))
                    continue

                outLine = "\t".join(outFields)
                dh.write(f"{outLine}\n")
                if afterLine:
                    dh.write(afterLine)
                    afterLine = ""

        if unmatchedLines:
            print(f"{len(unmatchedLines)} unmatched lines")
            for (i, error, line) in unmatchedLines[0:100]:
                print(f"line {i:>7}: ({error.strip()}) {line}")
        else:
            print("All lines recognized")
        if len(nest):
            print(f"At end (line {i}): stack not empty: {len(nest)} elements")
            print(", ".join(nest[0:100]))
        else:
            print("OK")

    def read(self):
        C = self.C

        cur = {
            PAGE: 0,
            PHOTO: 0,
            TABLE: 0,
            TR: 0,
            TD: 0,
            AREA: 0,
            PARA: 0,
            LINE: 0,
            WORD: 0,
            CHAR: 0,
        }
        amount = {
            PAGE: 0,
            PHOTO: 0,
            TABLE: 0,
            TR: 0,
            TD: 0,
            AREA: 0,
            PARA: 0,
            LINE: 0,
            WORD: 0,
            CHAR: 0,
        }
        simpleSource = self.simpleSource
        self.amount = amount
        boundaryFixes = set()
        self.boundaryFixes = boundaryFixes
        simplified = []
        self.simplified = simplified

        spaceWidths = collections.Counter()

        print("Reading HOCR simplified source")

        with open(simpleSource) as fh:
            thinSpace = False
            thinSpaces = 0
            thinSpaceThreshold = C.thinSpaceThreshold
            j = 0

            for (i, line) in enumerate(fh):
                fields = line.strip("\n").split("\t")
                content = fields[0]
                if line.startswith("∪"):
                    container = content[1:]
                    if container == PAGE:
                        amount[PAGE] += 1
                        cur[AREA] = 0
                        cur[PARA] = 0
                        cur[LINE] = 0
                        cur[WORD] = 0
                        cur[CHAR] = 0
                    elif container in {AREA, TD}:
                        amount[AREA] += 1
                        cur[PARA] = 0
                        cur[WORD] = 0
                        cur[CHAR] = 0
                    elif container == PARA:
                        amount[PARA] += 1
                        cur[WORD] = 0
                        cur[CHAR] = 0
                    elif container == LINE:
                        amount[LINE] += 1
                        cur[WORD] = 0
                        cur[CHAR] = 0
                    elif container == WORD:
                        if not thinSpace:
                            amount[WORD] += 1
                            cur[CHAR] = 0
                elif line.startswith("∩"):
                    container = content[1:]
                    if container == WORD and thinSpace:
                        thinSpace = False
                        boundaryFixes.add(j)
                    else:
                        cur[container] += 1

                else:
                    amount[CHAR] += 1
                    box = fields[1].split("=")[1].split()
                    left = int(box[0])
                    right = int(box[2])
                    confidence = float(fields[2].split("=")[1])
                    width = right - left
                    if content == " ":
                        thinSpace = width <= thinSpaceThreshold
                        spaceWidths[min((int(round(width / 10)) * 10, 200))] += 1
                    else:
                        thinSpace = False
                    if thinSpace:
                        cur[CHAR] -= 1
                        thinSpaces += 1
                    else:
                        simplified.append(
                            (
                                i + 1,
                                cur[PAGE],
                                cur[AREA],
                                cur[PARA],
                                cur[LINE],
                                cur[WORD],
                                cur[CHAR],
                                content,
                                confidence,
                                width,
                            )
                        )
                        j += 1

        for (w, n) in sorted(spaceWidths.items()):
            print(f"{n:>7} spaces with width {w:>2}")
        print(
            f"Inhibited {len(boundaryFixes)} word boundaries after a thin space"
            f" of <= {thinSpaceThreshold} px"
        )

        print("Statistics:")
        for (kind, n) in amount.items():
            if kind == CHAR:
                print(f"{kind:<10}: {n:>7} x minus {thinSpaces} = {n - thinSpaces}")
                print(
                    f"Is this equal to the resulting number of charachter records?"
                    f" {n - thinSpaces == len(simplified)}"
                )
            else:
                print(f"{kind:<10}: {n:>7} x")
        print("OK")

    def wordify(self):
        simplified = self.simplified
        boundaryFixes = self.boundaryFixes

        print("Chunking characters into words")

        curLine = None
        curWord = None
        curSection = None
        letters = ""
        sumConfidence = 0

        before = None

        rawWords = []
        self.rawWords = rawWords
        wordJoins = []
        self.wordJoins = wordJoins

        def step():
            if curWord is not None:
                avConfidence = sumConfidence / len(letters)
                (realLetters, punc) = wordRe.findall(letters)[0]
                if curLine != line and not punc.endswith(" "):
                    punc += " "

                rawWords.append(
                    (firstI, *curSection, curWord, realLetters, punc, avConfidence)
                )
                if before is not None:
                    wordJoins.append(
                        (len(rawWords), before, letters.removeprefix(before))
                    )

        for (
            j,
            (i, page, area, para, line, word, char, letter, confidence, width),
        ) in enumerate(simplified):
            if curLine is None:
                curLine = line
            if j in boundaryFixes:
                before = letters
            section = (page, area, para, line)
            newSection = curSection != section
            newWord = curWord != word
            if newWord or newSection:
                step()
                if before is not None:
                    before = None
                if newWord:
                    curWord = word
                if newSection:
                    curSection = section
                letters = ""
                sumConfidence = 0
                firstI = i

            letters += letter
            sumConfidence += float(confidence)
            curLine = line

        step()

        print(f"{len(rawWords)} raw words")

        print(f"{len(wordJoins)} word joins:")
        for (k, before, punc) in wordJoins[0:100]:
            print(f"line {k:>7}: {before} + {punc}")

    def clean(self):
        C = self.C
        rawWords = self.rawWords
        amount = self.amount
        frontPages = C.frontPages
        headerLines = C.headerLines
        diag = C.diag

        if not os.path.exists(diag):
            os.makedirs(diag, exist_ok=True)

        skips = set()

        if frontPages:
            pre = f"{frontPages} front pages and "
        print(f"Removing {pre}'Digitized by Google'")

        curPage = None
        entries = 0
        missed = 0
        headLines = collections.defaultdict(list)

        def step():
            nonlocal entries
            nonlocal missed

            if curPage is not None:
                skip = False
                prevs = []
                for k in range(j - 5, j):
                    if skip:
                        skips.add(k)
                    else:
                        letters = rawWords[k][6]
                        prevs.append(letters)
                        if (
                            distance(letters, "Digitized") < 3
                            or ratio(letters, "Digitizedby") > 0.6
                        ):
                            skips.add(k)
                            skip = True
                if skip:
                    entries += 1
                else:
                    print(f"Line {j - 1:>6} page {page - 1:>3}: {prevs}")
                    missed += 1

        for (
            j,
            (i, page, area, para, line, word, letters, punc, confidence),
        ) in enumerate(rawWords):
            if page <= frontPages:
                skips.add(j)
            else:
                if page != curPage:
                    step()
                    curPage = page
                if line <= headerLines.get(page, headerLines.get(0, 0)):
                    headLines[page].append((i, letters, punc))
                    skips.add(j)
        step()

        words = []
        self.words = words

        for (j, w) in enumerate(rawWords):
            if j not in skips:
                words.append(w)

        print(f"Missed 'Digitized by Google' {missed} x")
        print(f"Deleted 'Digitized by Google' {entries} x")
        print(f"Deleted the header line of {len(headLines)} pages")
        print(f"{len(words)} words")
        print(f"Not counting {len(skips)} skipped words")
        print(
            f"Did all other words make it into the word records?"
            f" {amount[WORD] - len(skips) == len(words)}"
        )
        hFile = f"{diag}/headlines.tsv"
        with open(hFile, "w") as dh:
            dh.write("index\tpage\ttext\n")

            for (page, headInfo) in headLines.items():
                letters = "".join(f"{info[1]}{info[2]}" for info in headInfo)
                start = headInfo[0][0]
                end = headInfo[-1][0]
                dh.write(f"{start}-{end}\t{page}\t{letters}\n")
        print(f"See {hFile} for removed header lines")

    def write(self):
        words = self.words
        dest = self.dest

        print("Writing word file as tsv")

        with open(dest, "w") as dh:
            for (i, page, area, para, line, word, letters, punc, confidence) in words:
                text = "\t".join(
                    (
                        str(i),
                        str(page),
                        str(area),
                        str(para),
                        str(line),
                        str(word),
                        letters,
                        punc,
                        f"{confidence:.1f}",
                    )
                )
                dh.write(f"{text}\n")
