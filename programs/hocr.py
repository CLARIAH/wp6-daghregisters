import os
import collections
import re
from textwrap import dedent

from Levenshtein import distance, ratio

from config import Config
from headconfig import Config as HeadConfig

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

MONTH_LAST = {
    1: 31,
    2: 28,
    3: 31,
    4: 30,
    5: 31,
    6: 30,
    7: 31,
    8: 31,
    9: 30,
    10: 31,
    11: 30,
    12: 31,
}


class Hocr:
    def __init__(self, volume):
        self.volume = volume
        self.good = self.config()

    def config(self):
        volume = self.volume

        C = Config()
        if not C.checkVolume(volume):
            return False

        self.C = C
        self.source = f"{C.local}/{C.volumeName(volume)}_chocr.html"
        self.simpleSource = f"{C.local}/{C.volumeName(volume)}_chocr.tsv"
        self.dest = f"{C.local}/{C.volumeName(volume)}_words.tsv"

        HC = HeadConfig()
        self.HC = HC

        return True

    def simplify(self):
        if not self.config():
            return

        source = self.source

        if not os.path.exists(source):
            print(f"Source file does not exist: {source}")

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
                    content = (
                        content.replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&apos;", "'")
                        .replace("&quot;", '"')
                        .replace("&amp;", "&")
                    )

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
        if not self.config():
            return

        simpleSource = self.simpleSource

        if not os.path.exists(simpleSource):
            print(f"Simpliefied source file does not exist: {simpleSource}")

        self.config()
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
            AREA: 0,
            PARA: 0,
            LINE: 0,
            WORD: 0,
            CHAR: 0,
        }
        other = {
            PHOTO: 0,
            TABLE: 0,
            TR: 0,
            TD: 0,
        }
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
                        if container == TD:
                            other[container] += 1
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
                    else:
                        other[container] += 1
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
        for (kind, n) in other.items():
            if kind == PHOTO:
                msg = "skipped"
            elif kind in {TABLE, TR}:
                msg = "ignored"
            elif kind == TD:
                msg = f"changed to {AREA}"
            else:
                msg = "OVERLOOKED!!!"
            print(f"{kind:<10}: {n:>7} x {msg}")
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
        if not self.config():
            return

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
        if not self.config():
            return

        volume = self.volume
        C = self.C
        HC = self.HC
        rawWords = self.rawWords
        amount = self.amount
        startPage = C.volumeInfo[volume]["startPage"]
        endPage = C.volumeInfo[volume]["endPage"]
        headLinePos = HC.lines[volume]

        skips = set()

        print(
            dedent(
                f"""
            Removing
            * The pages before page {startPage}
            * The pages after page {endPage}
            * the strings Digitized by Google at the bottom of each page
            Saving and removing
            * The header lines of each page
            """.strip()
            )
        )

        curPage = None
        entries = 0
        missed = 0
        headWords = []

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
            if page < startPage or endPage >= 0 and page > endPage:
                skips.add(j)
            else:
                pageHeadLinePos = headLinePos.get(page, headLinePos.get(0, 0))
                if line <= pageHeadLinePos:
                    skips.add(j)
                    headWords.append((page, f"{letters}{punc}"))
                if page != curPage:
                    step()
                    curPage = page
        step()

        words = []
        self.words = words

        for (j, w) in enumerate(rawWords):
            if j not in skips:
                words.append(w)

        headLines = {}
        self.headLines = headLines
        for (page, word) in headWords:
            headLines.setdefault(page, []).append(word)
        for (page, wrds) in headLines.items():
            headLines[page] = " ".join(wrds)
        self.analyseHeads()

        print(f"Missed 'Digitized by Google' {missed} x")
        print(f"Deleted 'Digitized by Google' {entries} x")
        print(f"Separated {len(headWords)} words in {len(headLines)} header lines")
        print(f"{len(words)} words")
        print(f"Not counting {len(skips)} skipped words")
        print(
            f"Did all other words make it into the word records?"
            f" {amount[WORD] - len(skips) == len(words)}"
        )

    def analyseHeads(self, start=None, end=None, show=False):
        HC = self.HC
        volume = self.volume
        corrections = HC.getData("corrections", volume, {})
        monthsData = HC.getData("months", volume, {})
        months = monthsData["entries"]
        monthIndex = monthsData["index"]
        monthHints = HC.getData("monthHints", volume, {})
        dayHints = HC.getData("days", volume, {})
        dayGaps = HC.getData("dayGaps", volume, {})
        isRightStart = HC.getData("isRight", volume, {})

        headLines = self.headLines

        def matchMonth(word, show=False):
            word = word.lower()
            if word in monthHints:
                return monthHints[word]

            word = word.replace("ü", "u").replace("ë", "e").replace("é", "e")
            rs = []
            for (i, m) in enumerate(months):
                r = ratio(m, word)
                rs.append(r)

            theI = None
            maxR = max(rs)
            maxI = [i for i in range(len(rs)) if rs[i] == maxR][0]
            hiRep = ""
            if maxR >= 0.54:
                diff = 0.04 if maxR >= 0.7 else 0.09 if maxR >= 0.6 else 0.12
                threshold = maxR - diff
                highIs = [i for (i, r) in enumerate(rs) if r >= threshold]
                if len(highIs) == 1:
                    theI = maxI
                    hiRep = f" single match >= {threshold:>.2f}"
                else:
                    hiRep = f" {len(highIs)} matches >= {threshold:.2f}"

            if show:
                print(f"{word} best match {maxR:.2f} {hiRep}")
                for i in range(len(rs)):
                    print(
                        f"\t{'OK' if i == theI else 'XX'} ~{rs[i]:.2f} {months[i]:<12}"
                    )
            return None if theI is None else months[theI]

        def separate(word, show=False):
            if show:
                print(f"ORIG: {word}")
            for (occ, corr) in corrections.items():
                word = word.replace(occ, corr)
            if show:
                print(f"CORR: {word}")

            newWord = []
            prevC = None
            for c in word:
                if prevC is not None:
                    newWord.append(prevC)
                    if (
                        prevC.isalnum()
                        and not c.isalnum()
                        or not prevC.isalnum()
                        and c.isalnum()
                        and prevC != " "
                    ):
                        newWord.append(" ")
                prevC = c
            if prevC is not None:
                newWord.append(prevC)
            word = "".join(newWord)
            newWord = []
            prevC = None
            for c in word:
                if prevC is not None:
                    newWord.append(prevC)
                    if (
                        prevC.isalpha()
                        and not c.isalpha()
                        or not prevC.isalpha()
                        and c.isalpha()
                        and prevC != " "
                    ):
                        newWord.append(" ")
                prevC = c
            if prevC is not None:
                newWord.append(prevC)
            newWord = "".join(newWord)
            newWord = newWord.strip().split()
            newWord = " ".join(newWord)
            newWord = newWord.replace(" > ", ">")
            newWord = newWord.replace(" < ", "<")
            newWord = newWord.split()
            if show:
                print(f"SPLIT: {word}")
            return newWord

        def analyseHead(isRight, pageNum, curYear, show=False):
            side = "R" if isRight else "L"
            head = headLines[pageNum]
            words = separate(head, show=show)
            monthStr = ""
            pageNumbers = []
            dotSeen = False
            firstWord = True
            anno = ""
            yearStr = ""
            strings = []
            days = []

            month = ""
            dayFrom = ""
            dayTo = ""

            for word in words:
                if word in {".", ","}:
                    dotSeen = True
                    continue

                if not monthStr and len(word) > 3:
                    tryMonth = matchMonth(word, show=show)
                    if tryMonth:
                        monthStr = tryMonth
                        continue

                if word.lower() == "anno":
                    anno = word.lower()
                    continue

                if isRight:
                    if dotSeen and not pageNumbers:
                        pageNumbers.append(word)
                    else:
                        if anno and not yearStr:
                            yearStr = word
                        else:
                            strings.append(word)
                else:
                    if anno and not yearStr:
                        yearStr = word
                    elif firstWord and not pageNumbers:
                        pageNumbers.append(word)
                    else:
                        strings.append(word)

                firstWord = False

            if yearStr:
                curYear = yearStr

            if monthStr:
                if pageNum in dayHints:
                    days = dayHints[pageNum]
                else:
                    for s in strings:
                        if s == "n":
                            s = "11"
                        if s.lower() in {"en", "-", "—"}:
                            s = "-"
                            if days:
                                days[-1] += s
                            else:
                                days.append(s)
                        elif s.isdigit():
                            if days and days[-1].endswith("-"):
                                days[-1] += s
                            else:
                                days.append(s)
                    days = "".join(days)
                month = monthIndex[monthStr]
                days = days.split("-", 1)
                dayFrom = days[0]
                dayTo = days[0] if len(days) == 1 else days[1]
                ok = (
                    curYear.isdigit()
                    and 1500 <= int(curYear) <= 1800
                    and 1 <= month <= 12
                    and dayFrom.isdigit()
                    and 1 <= int(dayFrom) <= 31
                    and dayTo.isdigit()
                    and 1 <= int(dayTo) <= 31
                )
            else:
                curYear = ""
                ok = True

            okRep = "OK" if ok else "XX"
            return [pageNum, side, okRep, curYear, month, dayFrom, dayTo, head]

        headData = []
        self.headData = headData

        isRight = isRightStart
        curYear = ""

        for pageNum in sorted(headLines):
            if (
                start is not None
                and pageNum < start
                or end is not None
                and pageNum > end
            ):
                isRight = not isRight
                continue
            head = analyseHead(isRight, pageNum, curYear, show=show)
            if show:
                print(f"{head=}")
            headData.append(head)
            isRight = not isRight
            curYear = head[3]

        prevYear = None
        prevMonth = None
        prevDayTo = None

        print("Head analysis:")
        for data in headData:
            pageNum = data[0]
            gaps = dayGaps.get(pageNum, None)
            gapFrom = None
            gapTo = None
            if gaps:
                (gapFrom, gapTo) = (int(x) for x in gaps.split("-"))
            ok = data[2]
            (year, month, dayTo) = (
                prevYear,
                prevMonth,
                prevDayTo,
            )

            if ok != "XX":
                error = ""
                dateParts = data[3:7]
                for _ in [1]:
                    if any(dp != "" for dp in dateParts):
                        if not all(dp != "" for dp in dateParts):
                            error = "INCOMPLETE"
                            continue
                        (year, month, dayFrom, dayTo) = (int(x) for x in dateParts)
                        monthMax = MONTH_LAST[month]
                        if dayFrom > monthMax + 1:
                            error = "F"
                        if dayTo > monthMax + 1:
                            error += "T"
                        if error:
                            error = f"MMAX-{error}"
                            continue

                        if dayFrom > dayTo:
                            error = "INV-RNG"
                            continue

                        if prevYear is not None and year not in {
                            prevYear,
                            prevYear + 1,
                        }:
                            error += "Y"
                        if prevMonth is not None and month not in {
                            prevMonth,
                            1 if prevMonth == 12 else prevMonth + 1,
                        }:
                            error += "M"
                        if (
                            prevMonth is not None
                            and prevDayTo is not None
                            and dayFrom
                            not in {
                                prevDayTo,
                                prevDayTo + 1,
                                1
                                if prevDayTo >= MONTH_LAST[prevMonth]
                                else prevDayTo + 1,
                            }
                        ):
                            if (
                                gapFrom is None
                                or gapTo is None
                                or gapFrom != prevDayTo
                                or gapTo != dayFrom
                            ):
                                error += "D"
                        if error:
                            error = f"CONT-{error}"
                            continue
                if error:
                    data[2] = f"XX-{error}"
                    text = "\t".join(str(x) for x in data)
                    print(text)

            (prevYear, prevMonth, prevDayTo) = (year, month, dayTo)

        report = collections.Counter()
        for data in headData:
            report[data[2]] += 1
        print("Head analysis overview:")
        for (status, n) in sorted(report.items(), key=lambda x: (x[1], x[0])):
            print(f"\t{n:>4} pages: {status}")

    def write(self):
        if not self.config():
            return

        C = self.C
        volume = self.volume
        auxDir = f"{C.auxDir}/{C.volumeNameNum(volume)}"
        if not os.path.exists(auxDir):
            os.makedirs(auxDir, exist_ok=True)

        words = self.words
        headData = self.headData
        dest = self.dest
        aux = f"{auxDir}/heads.tsv"

        print(f"Writing word file as tsv: {dest}")

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

        print(f"Writing head line file as tsv: {aux}")

        with open(aux, "w") as ah:
            ah.write("page\tside\tok\tyear\tmonth\tdayfrom\tdaystart\traw\n")
            for entry in headData:
                text = "\t".join(str(f) for f in entry)
                ah.write(f"{text}\n")
