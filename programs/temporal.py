from tf.app import use
from config import Config

C = Config()


def addDates(volume):
    if not C.checkVolume(volume):
        return

    tag = f"{C.org}/{C.repo}/{C.relative}/{C.tfName}/{C.volumeNameNum}/{C.tfVersion}"
    A = use(f"{tag}:clone", checkout="clone")
