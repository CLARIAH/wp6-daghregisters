# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.13.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %load_ext autoreload
# %autoreload 2

import collections
import re
from Levenshtein import distance, ratio
from tfFromTsv import convert, loadTf
from tf.app import use
from hocr import Hocr

H = Hocr(4)

H.simplify()

H.read()

H.wordify()

H.clean()

H.write()

convert(4)

loadTf(4)

A = use("Dans-labs/clariah-dr/tf/daghregister/004/0.1:clone", checkout="clone", hoist=globals())

# Check for irregular headers

for p in F.otype.s("page"):
    head = F.head.v(p)
    pageNum = F.n.v(p)
    diag = None
    if not head:
        diag = "---"
    elif len(head) < 7:
        diag = head
    if diag is not None:
        print(f"Page {pageNum}: {diag}")
        lines = L.d(p, otype="line")[0:2]
        for line in lines:
            A.plain(line)

# +
CORRECTIONS = """
!^===N
^===
•iO===20
""".strip().split("\n")

corrections = {}
for line in CORRECTIONS:
    (occ, corr) = line.split("===")
    corrections[occ] = corr
# -

MONTHS = """
januariüs
februariüs
martiüs
april
mayus
juniüs
juliüs
augusto
september
october
november
december
""".strip().split()

# +
DAYS_PROTO = """
14: 10
42,44-46: 27
54: 28
58: 1-4
60-67: 9
68: 9-12
69: 13-19
72: 22
75: 28-31
76: 1-4
78: 10-14
79: 14
80: 14-16
81: 16-18
83: 18
90,93: 21
110: 27
119: 1-2
125: 6
133: 6-8
155-171: 31
173: 1-9
177: 15
186: 24
187: 24-29
188: 29
191: 1-2
195: 14-17
198-206: 19
208: 19-26
217: 1-4
218: 4-10
219,222: 10
224: 13-16
230: 31
234: 1-3
239-242: 3
249-253: 9
255,256: 11
262-267: 19
268: 19-20
269: 20-21
272,275: 21
281: 21-22
282: 22-27
283: 27-28
284: 28-29
286: 1
291: 9-10
303-309: 14
317: 14-15
323,330,335: 20
341: 23
346: 23-24
350: 26-29
351: 29
352: 29-30
354: 1-3
357: 8-12
360: 21-23
362: 27-28
364: 29-30
365: 1
366: 1-3
367: 3-6
369: 8-13
375: 24-25
378: 25
382,383: 28
387: 28-30
396: 1-3
400: 10-14
401: 14-15
405: 18-19
409: 20-24
411: 25-26
412: 26
416: 28-29
419: 1-2
426: 2
431: 2-4
435: 4-7
440: 7
444: 9-12
448: 14
454: 17-18
455: 18
462: 27-30
463,464: 1
469: 1-3
470-472,479: 3-7
480:  4-7
481:  7-8
487: 18-22
491: 30-31
495,496: 31
""".strip().split("\n")

DAYS = {}
for line in DAYS_PROTO:
    (k, v) = line.split(":")
    (k, v) = (k.strip(), v.strip())
    ranges = []
    if "," in k:
        ranges = k.split(",")
        for i in range(int(b), int(e) + 1):
            DAYS[i] = v
    else:
        ranges = [k]
    for rng in ranges:
        if "-" in rng:
            (b, e) = rng.split("-")
            for i in range(int(b), int(e) + 1):
                DAYS[i] = v
        else:
            DAYS[int(rng)] = v

# +
HINTS = """
februariüs
  FEBtiUAtllOS
mayus
  MAVrs
  MAYtis
  MAYtJ
juniüs
  Junlus
juliüs
  iULllJS
""".strip().split("\n")

hints = {}
curMonth = None
for line in HINTS:
    if line.startswith(" "):
        line = line.strip()
        if curMonth is None:
            print(f"WARNING: occurrence {occ} does not fall under a month")
        else:
            hints[line.lower()] = curMonth
    else:
        if line in MONTHS:
            curMonth = line
        else:
            print(f"WARNING: {curMonth:<12} is not a month")
            curMonth = None
    

# +
def matchMonth(word, show=False):
    word = word.lower()
    if word in hints:
        return hints[word]
    
    word = word.replace("ü", "u").replace("ë", "e").replace("é", "e")
    rs = []
    for (i, m) in enumerate(MONTHS):
        r = ratio(m, word)
        rs.append(r)
        
    theI = None
    maxR = max(rs)
    maxI = [i for i in range(len(rs)) if rs[i] == maxR][0]
    hiRep = ""
    if maxR >= 0.54:
        diff = 0.04 if maxR >= 0.7 else 0.09 if maxR >= 0.6 else 0.12
        threshold = maxR - diff
        highIs = [i for (i, r) in enumerate(rs) if r >=threshold]
        if len(highIs) == 1:
            theI = maxI
            hiRep = f" single match >= {threshold:>.2f}"
        else:
            hiRep = f" {len(highIs)} matches >= {threshold:.2f}"
        
    if show:
        print(f"{word} best match {maxR:.2f} {hiRep}")
        for i in range(len(rs)):
            print(f"\t{'OK' if i == theI else 'XX'} ~{rs[i]:.2f} {MONTHS[i]:<12}")
    return None if theI is None else MONTHS[theI]

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
            if prevC.isalnum() and not c.isalnum() or not prevC.isalnum() and c.isalnum() and prevC != " ":
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
            if prevC.isalpha() and not c.isalpha() or not prevC.isalpha() and c.isalpha() and prevC != " ":
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


# -

# Show all headers

# +
def analyseHead(isRight, p=None, pNum=None, show=False, buckets=None, noMonth=None):
    if pNum:
        p = T.nodeFromSection((4, pNum))
    if p is None:
        print("No page node or page number given")
        return ""
        
    side = "R" if isRight else "L"
    pageNum = F.n.v(p)
    head = F.head.v(p)
    words = separate(head, show=show)
    month = ""
    pageNumbers = []
    dotSeen = False
    firstWord = True
    anno = ""
    year = ""
    strings = []
    days = []
    ignored = []
    
    for word in words:
        if word in {".", ","}:
            dotSeen = True
            continue
            
        if not month and len(word) > 3:
            tryMonth = matchMonth(word, show=show)
            if tryMonth:
                month = tryMonth
                if buckets is not None:
                    buckets[month][word].append(pageNum)
                continue
                
        if word.lower() == "anno":
            anno = word.lower()
            continue
            
        if isRight:
            if dotSeen and not pageNumbers:
                pageNumbers.append(word)
            else:
                if anno and not year:
                    year = word
                else:
                    strings.append(word)
        else:
            if anno and not year:
                year = word
            elif firstWord and not pageNumbers:
                pageNumbers.append(word)
            else:
                strings.append(word)
                    
        firstWord = False
        
    if month:
        if pageNum in DAYS:
            days.append(str(DAYS[pageNum]))
            ignored = strings
            strings = []
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
                else:
                    ignored.append(s)
        strings = []
        ignoredRep = "!!! " + (" ".join(ignored)) if ignored else ""
        titleString = f"{anno:<4} {year:<4} {month:<15} {' '.join(days):20} {ignoredRep}"
    else:
        titleString = ' '.join(strings)
        
        
    if noMonth is not None and not month:
        noMonth.append((F.n.v(p), side, words))
        
    return f"{pageNum:>3} {side} [{','.join(pageNumbers):<10}] {titleString}"
        
def analyseHeads():
    buckets = collections.defaultdict(lambda: collections.defaultdict(list))
    noMonth = []
    illegalDays = collections.defaultdict(list)
    
    pages = []
    isRight = False

    for p in F.otype.s("page"):
        pages.append(analyseHead(isRight, p=p, buckets=buckets, noMonth=noMonth))
        isRight = not isRight
        
    for page in pages:
        print(page)
        
    print(f"{len(noMonth)} pages without month.")
    for (p, side, words) in noMonth:
        print(f"{p:>3} {side} {' '.join(words)}")

    for month in MONTHS:
        print(month)
        for (form, occs) in sorted(buckets.get(month, {}).items(), key=lambda x: (-len(x[1]), x[0])):
            occsExamples = ", ".join(str(p) for p in occs[0:3])
            print(f"\t{form} ({len(occs)} x) {occsExamples}")


# -

analyseHead(False, pNum=42, show=True)

analyseHeads()




