# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.13.1
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %%
# %load_ext autoreload
# %autoreload 2

# %% [markdown]
# # Word splitting
#
# We split words in parts that also occur separately in the corpus.
#
# The result is in a new feature, `letterx`, where the wordsplit positions are marked with `┼`.

# %%
from tf.app import use
from splitting import splitupx

# %%
A = use("CLARIAH/wp6-daghregisters:clone", checkout="clone", hoist=globals())

# %%
words = [F.letters.v(w) for w in range(1, F.otype.maxSlot + 1)]

# %%
newWords = splitupx(words)

# %%
A.TF.save(
    nodeFeatures=dict(letterx={i + 1: newWords[i] for i in range(F.otype.maxSlot)}),
    metaData=dict(letterx=dict(valueType="str", description="word with split points marked by ┼")),
)

# %%
