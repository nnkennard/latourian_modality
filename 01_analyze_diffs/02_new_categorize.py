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
from nltk.stem import *

import scc_lib


def get_surface(tokens, with_spaces=False):
    surface = "".join(tokens).replace("-", "")
    return surface.replace("ﬁ", "fi")


def is_spacing_hyphenation(old_surface, new_surface):
    return old_surface == new_surface

def is_non_alphabetic(old_surface, new_surface):
    chars = old_surface + new_surface
    alpha_chars = [x for x in chars if x.isalpha()]
    return len(alpha_chars) < len(chars) / 2

def load_counts(min_count=0):
    counts = {}
    with open('counts.txt', 'r') as f:
        for line in f:
            token, count = line.split()
            counts[token] = int(count)
    return counts


TYPO_EDIT_DISTANCE = 3
STEMMER = PorterStemmer()

def is_typographical(old_token, new_token, spell_check_counts):
    if edit_distance(old_token, new_token) < TYPO_EDIT_DISTANCE:
        old_count = spell_check_counts.get(old_token.lower())
        new_count = spell_check_counts.get(new_token.lower())
        if old_count is None and new_count is not None:
            return True  # Old word is not a word, new word is a word
    if STEMMER.stem(old_token) == STEMMER.stem(new_token):
        return True
    return False


def is_subsequence(needle, haystack):
    for i in range(len(haystack)):
        if haystack[i:i + len(needle)] == needle:
            return True
    return False


def is_within_sentence(d, source_sentence_list, dest_sentence_list):
    """Diff is considered within sentence if old and new subsequences each fall
    within a sentence."""

    if d['old'] and d['new'] and d['old'][0] == d['new'][0] == '.':
        old = d['old'][1:]
        new = d['new'][1:]
    else:
        old, new = d['old'], d['new']

    for s_s in source_sentence_list:
        if is_subsequence(old, s_s):
            for s_d in dest_sentence_list:
                if is_subsequence(new, s_d):
                    #print(d)
                    #print(" ".join(s_s))
                    #print(" ".join(s_d))
                    #print()
                    return True
    return False


def get_diff_type(d, obj, spell_check_counts):
    old_surface = get_surface(d['old'])
    new_surface = get_surface(d['new'])
    if is_spacing_hyphenation(old_surface, new_surface):
        return "NON_DIFF"

    lengths = (len(d['old']), len(d['new']))
    if is_non_alphabetic(old_surface, new_surface):
        return "NONALPHA"
    if lengths == (1, 1):
        if is_typographical(*d['old'], *d['new'], spell_check_counts):
            return "TYPO"
        else:
            return "WORD_CHANGE"
    elif lengths == (1, 0):
        return "DELETE_WORD"
    elif lengths == (1, 2) and d['old'][0] == d['new'][0]:
        return "INSERT_WORD"
    else:
        if is_within_sentence(d, obj['tokens']['source'],
                              obj['tokens']['dest']):
            return "WITHIN_SENTENCE"
        else:
            return "MULTI_SENTENCE"


def filter_diffs(filename, spell_check_counts):
    diffs_by_type = collections.defaultdict(list)
    with open(filename, 'r') as f:
        obj = json.load(f)
        for d in obj['diffs']:
            diff_type = get_diff_type(d, obj, spell_check_counts)
            #if diff_type in ["WORD_CHANGE", "INSERT_WORD", "DELETE_WORD"]:
            #if diff_type in ["NONALPHA"]:
            _ = """
                print("-" * 80)
                print(" ".join(d['old']))
                print(" ".join(d['new']))
                print("-" * 80)
                print()"""
            print(diff_type)
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
    spell_check_counts = load_counts(100)
    for section in ['abstract', 'intro']:
        print(section)
        for forum in tqdm.tqdm(diffs_tried_forums):
            if not forum[f'{section}_status'] == 'complete':
                continue
            filenames = scc_lib.get_filenames(DATA_DIR, conference,
                                              forum['forum_id'])
            filtered_diffs = filter_diffs(filenames._asdict()[section],
                                          spell_check_counts)
            with open(filenames._asdict()[section], 'r') as f:
                obj = json.load(f)
                total += len(obj['diffs'])
            non_typos += len(filtered_diffs)
