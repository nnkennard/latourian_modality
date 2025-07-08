DATA_DIR = "/gypsum/work1/mccallum/nnayak/latmod/"
RECORDS_DIR = ("/work/pi_mccallum_umass_edu/nnayak_umass_edu/"
               "latourian_modality/00_extract_data/records/")

import collections
import json
import pickle
import tqdm

from nltk.corpus import words
from nltk.metrics.distance import edit_distance
from nltk.util import ngrams

import scc_lib
from spellcheck import CountTrie, TrieNode


def get_surface(tokens, with_spaces=False):
    surface = "".join(tokens).replace("-", "")
    return surface.replace("ﬁ", "fi")


def is_spacing_hyphenation(old_surface, new_surface):
    return old_surface == new_surface


with open('spellcheck.pkl', 'rb') as f:
    SPELL_CHECK_TRIE = pickle.load(f)

TYPO_EDIT_DISTANCE = 3
REAL_SPELLING_THRESHOLD = 10


def is_typographical(old_token, new_token):
    if edit_distance(old_token, new_token) < TYPO_EDIT_DISTANCE:
        old_is_in, old_count = SPELL_CHECK_TRIE.find(old_token)
        new_is_in, new_count = SPELL_CHECK_TRIE.find(new_token)
        return (new_is_in
                and (not old_is_in or old_count < REAL_SPELLING_THRESHOLD))


def get_diff_type(d, obj):
    old_surface = get_surface(d['old'])
    new_surface = get_surface(d['new'])
    if is_spacing_hyphenation(old_surface, new_surface):
        return "NON_DIFF"

    lengths = (len(d['old']), len(d['new']))
    if lengths == (1, 1):
        if is_typographical(*d['old'], *d['new']):
            print("TYPO", d)
            return "TYPO"
        else:
            print("WORD_CHANGE", d)
            return "WORD_CHANGE"

    return "ETC"


def filter_diffs(filename):
    diffs_by_type = collections.defaultdict(list)
    with open(filename, 'r') as f:
        obj = json.load(f)
        for d in obj['diffs']:
            diff_type = get_diff_type(d, obj)
            diffs_by_type[diff_type].append(d)
        return diffs_by_type


total = 0
non_typos = 0
for conference in scc_lib.Conference.ALL:
    print(conference)
    diffs_tried_forums = scc_lib.get_records(RECORDS_DIR,
                                             conference,
                                             scc_lib.Stage.COMPUTE,
                                             full_records=True)
    for section in ['abstract', 'intro']:
        print(section)
        for forum in tqdm.tqdm(diffs_tried_forums):
            if not forum[f'{section}_status'] == 'complete':
                continue
            filenames = scc_lib.get_filenames(DATA_DIR, conference,
                                              forum['forum_id'])
            filtered_diffs = filter_diffs(filenames._asdict()[section])
            with open(filenames._asdict()[section], 'r') as f:
                obj = json.load(f)
                total += len(obj['diffs'])
            non_typos += len(filtered_diffs)
