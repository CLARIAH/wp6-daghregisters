import collections

from tf.fabric import Fabric
from tf.convert.walker import CV
from tf.core.helpers import unexpanduser

from config import Config

C = Config()

SEP = "\t"

SLOT_TYPE = "word"

GENERIC = (
    dict(
        language="nld",
        institute="CLARIAH-Huygens-INT-DANS",
        project="daghregister",
        researcher="Lodewijk Petram",
        converters="Dirk Roorda",
        sourceFormat="HTML => TSV (tab-separated)",
    )
    | C.seriesInfo
)

OTEXT = {
    "fmt:text-orig-full": "{letters}{punc} ",
    "sectionFeatures": "n,n,n",
    "sectionTypes": "volume,page,line",
}

TYPE_MAP = ["page", "para", "line"]

INT_FEATURES = {"n", "year", "month", "dayfrom", "dayto"}

FEATURE_META = {
    "years": {
        "description": "years covered by the volume",
        "format": "string, comma-separated list of 4-digit years",
    },
    "n": {
        "description": ("sequence number of a volume, page, line"),
        "format": "number",
    },
    "letters": {
        "description": "text string of a word without punctuation",
        "format": "string",
    },
    "punc": {
        "description": "punctuation and/or space immediately after a word",
        "format": "string",
    },
    "side": {
        "description": "whether the page is a left or right page",
        "format": "string, either L or R",
    },
    "head": {
        "description": "raw contents of the header line of each page",
        "format": "string",
    },
    "year": {
        "description": "year covered by a page",
        "format": "integer",
    },
    "month": {
        "description": "month covered by a page",
        "format": "integer",
    },
    "dayfrom": {
        "description": "first day covered by a page",
        "format": "integer",
    },
    "dayto": {
        "description": "last day covered by a page",
        "format": "integer",
    },
}


def convert(volume):
    global VOLUME
    global SRC_FILE
    global HEADER_FILE

    if not C.checkVolume(volume):
        return

    VOLUME = volume

    SRC_FILE = f"{C.local}/{C.volumeName(VOLUME)}_words.tsv"
    HEADER_FILE = f"{C.auxDir}/{C.volumeNameNum(volume)}/heads.tsv"

    tfVersion = C.tfVersion
    tfDir = f"{C.tfDir}/{VOLUME:>03}"
    DEST = f"{tfDir}/{tfVersion}"
    cv = CV(Fabric(locations=DEST))

    return cv.walk(
        director,
        SLOT_TYPE,
        otext=OTEXT,
        generic=GENERIC | C.volumeInfo[VOLUME],
        intFeatures=INT_FEATURES,
        featureMeta=FEATURE_META,
        generateTf=True,
    )


# DIRECTOR


def director(cv):
    """Read tsv data fields.

    This is a function that does the work as indicated in the
    [walker converion engine of Text-Fabric](https://annotation.github.io/text-fabric/tf/convert/walker.html)
    See `fusus.convert` for a description of the fields in the TSV files.
    """

    errors = collections.defaultdict(set)

    cur = [None, None, None]
    prev = [None, None, None]
    nSec = len(prev)

    data = []

    with open(SRC_FILE) as fh:
        next(fh)
        for line in fh:
            row = line.rstrip("\n").split(SEP)[1:]
            page = int(row[0])
            para = int(row[2])
            line = int(row[3])
            letters = row[5]
            punc = row[6]
            conf = row[7]
            row = (page, para, line, letters, punc, conf)
            data.append(row)

    headerLines = {}

    with open(HEADER_FILE) as fh:
        next(fh)
        for line in fh:
            (pageNum, side, okRep, year, month, dayFrom, dayTo, head) = line.rstrip(
                "\n"
            ).split("\t")

            headerLines[int(pageNum)] = dict(
                side=side,
                year=int(year) if year else None,
                month=int(month) if month else None,
                dayfrom=int(dayFrom) if dayFrom else None,
                dayto=int(dayTo) if dayTo else None,
                head=head if head else None,
            )

    vol = cv.node("volume")
    cv.feature(vol, n=VOLUME, years=C.volumeInfo[VOLUME]["years"])
    s = None

    for (r, fields) in enumerate(data):
        for i in range(nSec):
            if fields[i] != prev[i]:
                for j in reversed(range(i, nSec)):
                    cv.terminate(cur[j])
                    prev[j] = 0
                for j in range(i, nSec):
                    cn = cv.node(TYPE_MAP[j])
                    cv.feature(cn, n=fields[j])
                    if j == 0:
                        cv.feature(cn, **headerLines[fields[j]])
                    cur[j] = cn
                break
        for i in range(nSec):
            prev[i] = fields[i]

        letters = fields[3]
        punc = fields[4]
        if letters == "":
            previousPunc = cv.get("punc", s)
            if not previousPunc.endswith(" ") or not punc.startswith(" "):
                punc = f"{previousPunc}{punc}"
            cv.feature(s, punc=punc)
            continue

        parts = letters.split(",")
        lastPart = len(parts) - 1
        for (i, part) in enumerate(parts):
            if part == "":
                continue
            thisPunc = punc if i == lastPart else ", "
            s = cv.slot()
            if len(part) > 2 and (
                part[0] == "'"
                and part[1].lower() in {"s", "t"}
                or part[0].lower() in {"d", "t"}
                and part[1] == "'"
            ):
                cv.feature(s, letters=part[0:2], punc=" ")
                s = cv.slot()
                cv.feature(s, letters=part[2:], punc=thisPunc)
            else:
                cv.feature(s, letters=part, punc=thisPunc)

    for i in reversed(range(nSec)):
        if cur[i]:
            cv.terminate(cur[i])

    cv.terminate(vol)

    for feat in FEATURE_META:
        if not cv.occurs(feat):
            cv.meta(feat)

    if errors:
        for kind in sorted(errors):
            instances = sorted(errors[kind])
            nInstances = len(instances)
            showInstances = instances[0:20]
            print(f"ERROR {kind}: {nInstances} x")
            print(", ".join(showInstances))


# TF LOADING (to test the generated TF)


def loadTf(volume, silent=False):
    if not C.checkVolume(volume):
        return

    VOLUME = volume

    tfVersion = C.tfVersion
    tfDir = f"{C.tfDir}/{C.volumeNameNum(VOLUME)}"
    DEST = f"{tfDir}/{tfVersion}"
    print(f"Loading tf data from {unexpanduser(DEST)}")

    TF = Fabric(locations=[DEST], silent=True)
    allFeatures = TF.explore(silent=True, show=True)
    loadableFeatures = allFeatures["nodes"] + allFeatures["edges"]
    api = TF.load(loadableFeatures, silent=silent)
    if api and not silent:
        print(f"max node = {api.F.otype.maxNode}")
        print("Frequencies of words")
        for (word, n) in api.F.letters.freqList()[0:20]:
            print(f"{n:>6} x {word}")
    return TF
