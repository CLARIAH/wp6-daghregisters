import collections

from tf.fabric import Fabric
from tf.convert.walker import CV

from config import Config

C = Config()

SEP = "\t"

SLOT_TYPE = "word"

GENERIC = dict(
    language="nld",
    institute="CLARIAH-Huygens-INT-DANS",
    project="daghregister",
    researcher="Lodewijk Petram",
    converters="Dirk Roorda",
    sourceFormat="HTML => TSV (tab-separated)",
) | C.seriesInfo

OTEXT = {
    "fmt:text-orig-full": "{letters}{punc} ",
    "sectionFeatures": "n,n,n",
    "sectionTypes": "volume,page,line",
}

TYPE_MAP = ["page", "para", "line"]

INT_FEATURES = {"n"}

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
    "head": {
        "description": "contents of the header line of each page",
        "format": "string",
    },
}


def convert(volume):
    global VOLUME
    global SRC_FILE

    if not C.checkVolume(volume):
        return

    VOLUME = volume

    SRC_FILE = f"{C.local}/{C.volumeName(VOLUME)}_words.tsv"

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

    headerLines = C.volumeInfo[VOLUME]["headerLines"]

    errors = collections.defaultdict(set)

    cur = [None, None, None]
    prev = [None, None, None]
    nSec = len(prev)

    def getData(dataFile, sep):
        data = []

        with open(dataFile) as fh:
            next(fh)
            for line in fh:
                row = line.rstrip("\n").split(sep)[1:]
                page = int(row[0])
                para = int(row[2])
                line = int(row[3])
                letters = row[5]
                punc = row[6]
                conf = row[7]
                row = (page, para, line, letters, punc, conf)
                data.append(row)
        return data

    data = getData(SRC_FILE, SEP)

    vol = cv.node("volume")
    cv.feature(vol, n=VOLUME, years=C.volumeInfo[VOLUME]["years"])
    curHead = None

    for (r, fields) in enumerate(data):
        for i in range(nSec):
            if fields[i] != prev[i]:
                for j in reversed(range(i, nSec)):
                    cv.terminate(cur[j])
                    prev[j] = 0
                if i == 0:
                    page = fields[i]
                    pageHeaderLines = headerLines.get(page, headerLines.get(0, 0))
                for j in range(i, nSec):
                    isLine = j == 2
                    isHead = isLine and fields[j] <= pageHeaderLines
                    if isHead:
                        if fields[j] == 1:
                            curHead = ""
                    else:
                        cn = cv.node(TYPE_MAP[j])
                        cv.feature(cn, n=fields[j])
                        cur[j] = cn
                        if isLine and curHead is not None:
                            cv.feature(cur[0], head=curHead.strip())
                            curHead = None
                break
        for i in range(nSec):
            prev[i] = fields[i]

        letters = fields[3]
        punc = fields[4]

        if curHead is None:
            s = cv.slot()
            cv.feature(s, letters=letters, punc=punc)
        else:
            curHead += f" {letters}{punc}"
    if curHead is not None:
        cv.feature(cur[0], head=curHead)

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


def loadTf(volume):
    if not C.checkVolume(volume):
        return

    VOLUME = volume

    tfVersion = C.tfVersion
    tfDir = f"{C.tfDir}/{C.volumeNameNum(VOLUME)}"
    DEST = f"{tfDir}/{tfVersion}"

    TF = Fabric(locations=[DEST])
    allFeatures = TF.explore(silent=True, show=True)
    loadableFeatures = allFeatures["nodes"] + allFeatures["edges"]
    api = TF.load(loadableFeatures, silent=False)
    if api:
        print(f"max node = {api.F.otype.maxNode}")
        print("Frequencies of words")
        for (word, n) in api.F.letters.freqList()[0:20]:
            print(f"{n:>6} x {word}")
