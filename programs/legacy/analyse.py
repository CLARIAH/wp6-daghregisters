import collections
import re

from config import Config


C = Config()
SOURCE = f"{C.local}/{C.name}_chocr.html"
DEST = f"{C.local}/{C.name}_divs.txt"

elemClassRe = re.compile(r'''^<(\S+) class="([^"]*)''')

elems = collections.Counter()


with open(SOURCE) as fh, open(DEST, "w") as dh:
    for line in fh:
        line = line.strip()
        match = elemClassRe.match(line)
        if match:
            elem = match.group(1)
            cls = match.group(2)
            elems[f"{elem}.{cls}"] += 1

    for (tag, n) in sorted(elems.items()):
        dh.write(f"{n:>7} x {tag}\n")
