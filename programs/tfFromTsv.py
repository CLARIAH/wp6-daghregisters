import collections

from tf.fabric import Fabric
from tf.convert.walker import CV

from config import Config


SLOT_TYPE = "word"

GENERIC = dict(
    language="nld",
    institute="CLARIAH-Huygens-INT-DANS",
    project="daghregister",
    researcher="Lodewijk Petram",
    converters="Dirk Roorda",
    sourceFormat="HTML => TSV (tab-separated)",
)

OTEXT = {
    "fmt:text-orig-full": "{letters}{punc} ",
    "sectionFeatures": "n,n,n",
    "sectionTypes": "volume,page,line",
}

TYPE_MAP = ["page", "para", "line"]

INT_FEATURES = {"n"}

FEATURE_META = {
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
}


def convert():
    global VOLUME
    global SRC_FILE
    global SEP

    C = Config()

    volume = C.name[-3:]
    VOLUME = int(volume.lstrip("0"))
    SRC_FILE = f"{C.local}/{C.name}_words.tsv"
    tfVersion = C.tfVersion
    tfDir = f"{C.tfDir}/{volume}"
    dest = f"{tfDir}/{tfVersion}"

    SEP = "\t"

    cv = CV(Fabric(locations=dest))

    return cv.walk(
        director,
        SLOT_TYPE,
        otext=OTEXT,
        generic=GENERIC,
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
    cv.feature(vol, n=VOLUME)

    for (r, fields) in enumerate(data):
        for i in range(nSec):
            if fields[i] != prev[i]:
                for j in reversed(range(i, nSec)):
                    cv.terminate(cur[j])
                for j in range(i, nSec):
                    cn = cv.node(TYPE_MAP[j])
                    cv.feature(cn, n=fields[j])
                    cur[j] = cn
                break
        for i in range(nSec):
            prev[i] = fields[i]

        letters = fields[3]
        punc = fields[4]

        s = cv.slot()
        cv.feature(s, letters=letters, punc=punc)

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


def loadTf():
    C = Config()

    volume = C.name[-3:]
    tfVersion = C.tfVersion
    tfDir = f"{C.tfDir}/{volume}"
    dest = f"{tfDir}/{tfVersion}"

    TF = Fabric(locations=[dest])
    allFeatures = TF.explore(silent=True, show=True)
    loadableFeatures = allFeatures["nodes"] + allFeatures["edges"]
    api = TF.load(loadableFeatures, silent=False)
    if api:
        print(f"max node = {api.F.otype.maxNode}")
        print("Frequencies of words")
        for (word, n) in api.F.letters.freqList()[0:20]:
            print(f"{n:>6} x {word}")
