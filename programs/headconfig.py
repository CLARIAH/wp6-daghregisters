lines_004 = """
0: 1
43: 2
159: 2
341: 2
390: 2
498: 3
499-523: 2
"""

isRight_004 = """
True
"""

corrections_004 = """
!^===N
^===
•iO===20
"""

months_ALL = """
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
"""

monthHints_ALL = """
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
"""

dayGaps_004 = """
57: 28-30
78: 7-10
119: 29-1
294: 11-13
375: 22-24
"""

days_004 = """
14: 10
30: 25-27
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
280: 21
281: 21-22
282: 22-27
283: 27-28
284: 28-29
286: 1
291: 9-10
303-309: 14
317: 14-15
318: 15
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
470-479: 3
480:  4-7
481:  7-8
487: 18-22
491: 30-31
495,496: 31
"""


def toBool(data, volume, string):
    value = string.strip()
    return value == "True"


def toDict(data, volume, string, valueConvert, sep):
    store = {}
    for line in string.strip().split("\n"):
        (k, v) = line.split(sep)
        v = valueConvert(v)
        store[k] = v
    return store


def toRangeDict(data, volume, string, valueConvert):
    store = {}
    for line in string.strip().split("\n"):
        (k, v) = line.split(":")
        (k, v) = (k.strip(), v.strip())
        v = valueConvert(v)
        ranges = k.split(",")
        for rng in ranges:
            if "-" in rng:
                (b, e) = rng.split("-")
                for i in range(int(b), int(e) + 1):
                    store[i] = v
            else:
                store[int(rng)] = v
    return store


def toEntriesIndex(data, volume, string):
    entries = string.strip().split("\n")
    index = {entry: i + 1 for (i, entry) in enumerate(entries)}
    return dict(entries=entries, index=index)


def toBuckets(data, volume, string, kind):
    valueIndex = getattr(data, kind)[volume]["index"]
    buckets = {}
    curBucket = None

    for line in string.strip().split("\n"):
        if line.startswith(" "):
            line = line.strip()
            if curBucket is None:
                print(f"WARNING: occurrence {line} does not fall under a bucket")
            else:
                buckets[line.lower()] = curBucket
        else:
            if line in valueIndex:
                curBucket = line
            else:
                print(f"WARNING: {curBucket:<12} is not a valid value")
                curBucket = None
    return buckets


processors = dict(
    lines=(toRangeDict, int),
    months=(toEntriesIndex,),
    monthHints=(toBuckets, "months"),
    days=(toRangeDict, str),
    dayGaps=(toRangeDict, str),
    corrections=(toDict, str, "==="),
    isRight=(toBool,),
)


class Config:
    def __init__(self):
        for (k, v) in globals().items():
            nameParts = k.split("_")
            if len(nameParts) != 2:
                continue
            (name, volume) = nameParts
            volume = volume.strip("0")
            if volume != "ALL" and not volume.isdigit():
                continue
            volume = 0 if volume == "ALL" else int(volume)
            store = getattr(self, name, None)
            if store is None:
                setattr(self, name, {})
                store = getattr(self, name)
            if name in processors:
                (processor, *args) = processors[name]
                v = processor(self, volume, v, *args)
            store[volume] = v

    def getData(self, key, volume, default):
        data = getattr(self, key, {})
        return data.get(volume, data.get(0, default))
