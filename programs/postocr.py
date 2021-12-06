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

# + [markdown] tags=[]
# # Post OCR
#
# When searching the Dagh Registers we are confronted with many different forms of the same words.
# There are three causes for that
#
# * OCR errors
# * spelling variations
# * morphology of the language
#
# We deal with them separately.
#
# ## Techniques
#
# To battle OCR errors, we work with letter 2,3-grams, filter them to retain
# only the ones that may occur in real words, distill a set of legal words,
# and then use an OCR key to search for corrections of illegal words.
#
# Against spelling variations we use an anagram key to pick the best representant
# among the variations in which a word occurs.
#
# To deal with morphology, we use the same anagram hash, but with other settings.
# -

# %load_ext autoreload
# %autoreload 2

# +
import collections
import re

from pocr import PostOcr
# -

# ## Read the corpus
#
# We read the corpus from its text-fabric representation and make an inventory of all the letterwise n-grams,
# n = 2,3.

P = PostOcr(4)
# P.charFreqs()

# + [markdown] tags=[]
# # OCR correction
#
# First task: distil a lexicon of good words from the corpus.
#
# Intuitition: make a list of the bi- and trigrams of letters, select the most freqent of these, and weed out the ones that 
# cannot be part of words and are clearly ocr mistakes.
#
# Then find all words in the corpus that consist of such bi- and trigrams.
#
# We will miss rare words of which no correct form exists in the corpus.
#
# We may try to correct such words by replacing their faulty bi- or trigrams by 
# looking up legal words with the same *ocr-key*.
# -

# Let's inspect the amount of word froms the the grams occur in.
# We take into account the frequencies of the words the n-grams occur in.

P.distFreq(2)

P.distFreq(3)

# Now for the word-starter grams:

P.distFreq(2, kind=False)

P.distFreq(3, kind=False)

# And for the word-ender grams:

P.distFreq(2, kind=True)

P.distFreq(3, kind=True)

# # Legal grams
#
# We try to weed out grams that cannot occur in real words.
# A first approximation is to spot illegal consonant combinations.
# We cannot do this for all the grams, but those that are at the start or end of words,
# can easily be detected by inspection.
#
# The first step is to show which consonant combinations occur.
#
# We collect all 2-grams that consist of two consonants at the start of words.
# Grams that only differ in case will be taken together.
#
# Note that we single out a set of grams consisting of a space and then two consonants.
# It is this set that we divide up into a legal subset and an illegal subset.
#
# There are other grams, even other starter grams that we do not deal with in this step.
#
# Above you see on each line the first letter of the combination with a `+` after it and its frequency above it.
# Then the second letter of the combination follows, with the frequency of the combination above it.

P.getCombis(False, 2)

# We have inspected all possibilities, sometimes by looking up occurrences in the pdf file of the corpus.
# That leads to a specification of which ones are the legal combinations.
# All other combinations will be deemed illegal.

LEGAL_START_BI_COMBIS_SPEC = """
s +tcplwnmj
c +lhrn
b +rlh
p +rlh
g +rhln
v +rl
t +rwhs
f +lr
d +rw
h +
w +rh
k +lrhn
r +h
j +
m +
l +
n +
q +
z +
x +
"""

P.legalizeCombis(False, 2, LEGAL_START_BI_COMBIS_SPEC)

# Now the same for 3-grams:

P.getCombis(False, 3)

LEGAL_START_TRI_COMBIS_SPEC = """
st -nptv
sc -blef
pr -óö
cl -èé
gr -r
br -f
vr -q
ch -mx
bl -
sp -dm
pl -
sl -xrc
tr -
tw -r
cr -n
fl -sgir
dr -
sw -
vl -
th -
gh +y
bh -i
fr -è
sn -clt
ph -h
sm -
ts +iu
gl -e
wr -
rh -
cn -i
gn -o
kl +e
kr -
dw -
kh -s
sj +o
kn -d
wh -
"""

P.legalizeCombis(False, 3, LEGAL_START_TRI_COMBIS_SPEC)

# Same exercition for combinations at the end of words.

P.getCombis(True, 2)

LEGAL_END_BI_COMBIS_SPEC = """
t -t
s -b
k +crl
h -lmnsw
x -rs
f -csdpt
p -snfhjqt
j -vf
d -cw
l +r
c +tnkl
b +r
z +sx
q +c
n +rjh
m +rl
g -
r +spjm
v +lt
w +r
"""

P.legalizeCombis(True, 2, LEGAL_END_BI_COMBIS_SPEC)

P.getCombis(True, 3)

LEGAL_END_TRI_COMBIS_SPEC = """
ck -dmbc
nt -nhmv
rt -écè
ch -p
ht -
rs - cö
gh -dhmpü
ns -c
ls -rnful
st -bdpü
ts -ft
dt -ó
ff -cë
lt -nfmé
cx -m
mp -bp
kt -
ft -cj
hs -e
mt -ócdl
pt -iu
th -dl
rd -c
rj -
nd -cl
tx -
tj -l
tc -
fs -i
ct -lt
lj -tls
dj -
sz -
bt -cg
cq -
rl +
ks -e
ms -oy
ps -
nj -
kx +
rm -
rp -
ng -y
wt -
ld -
rn -
cs -m
bj -
lf +
lp -
nc -ey
xt -
kj -
gs -f
sj -
lm -
gj -
lx -s
ds -dov
ws -
ph -o
vs -is
gt -
rk -
ss -a
xs -
lk -
rg +u
jn -st
js +i
kc -c
lc -
pp -
gd -n
hj -l
hn -
pj -
rb -
sd -
jr -
lv -
mj -
rf -
rw -
sr -v
tv -
xz -
"""

P.legalizeCombis(True, 3, LEGAL_END_TRI_COMBIS_SPEC)

# + [markdown] tags=[]
# ## Filter the set of n-grams
#
# We leave out grams that
#
# * are illegal because of the analysis of start- end end n-grams
# * have a too low frequency (except when they are legal by the step above)
# * have illegal characters in them
# * have upper case letters preceded by lowercase letters
#
# We might leave out legal grams in this process!
# -

LIMIT = {
    2: 10,
    3: 10,
}

P.getLegalGrams(LIMIT)

# + [markdown] tags=[]
# # Legal words
#
# We now distil the words that are legal, by selecting the words whose bi- and trigrams are all legal.
#
# In fact, we compute something slightly more general: for each word we compute its legality.
#
# The legality of a word is the percentage of legal grams with respect to the total number of grams in it.
# -

P.getLegalWords()

# + [markdown] tags=[]
# # OCR key
#
# We compute the OCR keys of all forms, in order to see whether illegal words have counterparts with the same OCR key that are legal.
# If so, we con choose the one with the minimum edit distance as a correction.
#
# The idea of *ocr-key* I learned from Kai Niklas's
# [Diplom Thesis](http://www.l3s.de/~tahmasebi/Diplomarbeit_Niklas.pdf).
# -

P.getOcrKey("amw")

# Let's make an index of the word forms by ocr key.

P.makeOcrIndex()

# + [markdown] tags=[]
# # Correction
#
# For every illegal word-like word we look to the legal words which share their ocr key with it.
# Some words are just numbers, or transcripts of symbols.
# We exclude them from the correctionprocess.
# Our first criterion for word-like is: the word has at least twice as much non-digits as digits.
#
# Of those words, we pick the ones that have the greatest similarity to the original word,
# provided they have at least a certain threshold similarity to that word.
# If there are several, we pick the word with the highest frequency.
# -


