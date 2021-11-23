import os

BASE = os.path.expanduser("~/github")
ORG = "Dans-labs"
REPO = "clariah-dr"
RELATIVE = "tf"
NAME = "daghregister001"
TF_NAME = "daghregister"

REPO_DIR = f"{BASE}/{ORG}/{REPO}"
LOCAL = f"{REPO_DIR}/_local"
DIAG = f"{REPO_DIR}/diagnostics"
TF_DIR = f"{REPO_DIR}/{RELATIVE}/{TF_NAME}"

FRONT_PAGES = 5
HEADER_LINES = {0: 1, 43: 2}
THIN_SPACE_THRESHOLD = 9

TF_VERSION = "0.1"


class Config:
    def __init__(self):
        self.org = ORG
        self.repo = REPO
        self.local = LOCAL
        self.diag = DIAG
        self.name = NAME
        self.frontPages = FRONT_PAGES
        self.headerLines = HEADER_LINES
        self.thinSpaceThreshold = THIN_SPACE_THRESHOLD
        self.relative = RELATIVE
        self.tfName = TF_NAME
        self.tfDir = TF_DIR
        self.tfVersion = TF_VERSION
