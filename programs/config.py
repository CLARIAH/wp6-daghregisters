import os

BASE = os.path.expanduser("~/github")
ORG = "Dans-labs"
REPO = "clariah-dr"
RELATIVE = "tf"
NAME = "daghregister001"
TF_NAME = "daghregister"

REPO_DIR = f"{BASE}/{ORG}/{REPO}"
LOCAL = f"{REPO_DIR}/_local"
TF_DIR = f"{REPO_DIR}/{RELATIVE}/{TF_NAME}"
AUX_DIR = f"{REPO_DIR}/aux/{TF_NAME}"
POST_DIR = f"{REPO_DIR}/postocr/{TF_NAME}"

SERIES_INFO = dict(
    fileName="daghregister",
    title="Dagh-Register",
    subtitle=(
        "gehouden int Casteel Batavia "
        "vant passerende daer ter plaetse als over geheel Nederlandts-India"
    ),
)
VOLUME_INFO = {
    4: dict(
        volume="Anno 1640-1641",
        years="1640,1641",
        editor=(
            "Uitgegeven door het Bataviaasch Genootschap van Kunsten en Wetenschappen, "
            "met medewerking van de Nederlandsch-Indische Regering en onder toezicht van "
            "Mr. J.A. van der Chijs"
        ),
        publisher="Batavia Landsdrukkerij and M. Nijhoff, 's Hage",
        published="1887",
        startPage=14,
        endPage=496,
    ),
}

THIN_SPACE_THRESHOLD = 9

TF_VERSION = "0.1"


class Config:
    def __init__(self):
        self.org = ORG
        self.repo = REPO
        self.local = LOCAL
        self.name = NAME
        self.thinSpaceThreshold = THIN_SPACE_THRESHOLD
        self.seriesInfo = SERIES_INFO
        self.volumeInfo = VOLUME_INFO
        self.relative = RELATIVE
        self.tfName = TF_NAME
        self.tfDir = TF_DIR
        self.auxDir = AUX_DIR
        self.postDir = POST_DIR
        self.tfVersion = TF_VERSION

    def checkVolume(self, volume):
        volumes = sorted(self.volumeInfo.keys())
        minVol = min(volumes)
        maxVol = max(volumes)

        if volume is None or type(volume) is not int or volume < minVol or volume > maxVol:
            print(f"Specify a volume as an integer between {minVol} and {maxVol}")
            return False
        if volume not in self.volumeInfo:
            print("No information for this volume specified")
            return False

        return True

    def volumeNameNum(self, volume):
        return f"{volume:>03}"

    def volumeName(self, volume):
        seriesName = self.seriesInfo["fileName"]
        return f"{seriesName}{volume:>03}"
