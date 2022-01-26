from itertools import chain
import collections


def getFreqs(words):
    freqs = collections.Counter()
    for word in words:
        freqs[word] += 1
    return freqs


def splitup(r, words):
    chunks = list(chain.from_iterable(word.split("┼") for word in words))
    allChunks = sorted(
        {chunk for chunk in chunks if not (chunk.startswith("⁼") or chunk.isdigit())}
    )

    freqs = getFreqs(chunks)
    chunkSplits = collections.defaultdict(dict)

    nHapaxes = sum(1 for (c, f) in freqs.items() if f == 1)
    print(f"Round {r} start: {len(allChunks)} distinct word-like chunks")
    print(f"{nHapaxes} hapaxes")

    for chunk in allChunks:
        cn = len(chunk)
        if cn < 6:
            continue
        maxQ = None
        (chunk1Best, chunk2Best) = (None, None)
        for s in range(2, cn - 1):
            chunk1 = chunk[0:s]
            chunk2 = chunk[s:]

            chunk1C = freqs[chunk1]
            chunk2C = freqs[chunk2]

            if chunk1C < 3 or chunk2C < 3:
                continue
            q = (chunk1C - 1) * (chunk2C - 1)
            if q:
                if maxQ is None or maxQ < q:
                    maxQ = q
                    (chunk1Best, chunk2Best) = (chunk1, chunk2)
        if maxQ:
            chunkSplits[chunk] = (chunk1Best, chunk2Best)

    print(f"Round {r}: {len(chunkSplits)} splits")

    newWords = []
    allChunks = set()

    for word in words:
        chunks = []
        for chunk in word.split("┼"):
            if chunk.startswith("⁼"):
                chunks.append(chunk)
            elif chunk.isdigit():
                chunks.append(f"⁼{chunk}")
            elif chunk in chunkSplits:
                chunks.extend(chunkSplits[chunk])
            else:
                chunks.append(chunk)
        newWords.append("┼".join(chunks))
        allChunks |= set(chunks)
    print(f"Round {r} end: {len(allChunks)} distinct word-like chunks")
    return (len(chunkSplits), newWords)


def splitupx(words):
    newWords = words
    r = 0
    while True:
        r += 1
        (nSplits, newWords) = splitup(r, newWords)
        if nSplits < 1:
            break
    return newWords
