DATA_DIR = "/gypsum/work1/mccallum/nnayak/latmod/"
RECORDS_DIR = ("/work/pi_mccallum_umass_edu/nnayak_umass_edu/"
               "latourian_modality/00_extract_data/records/")

import json
import scc_lib

from nltk.corpus import words
from nltk.metrics.distance import edit_distance
from nltk.util import ngramswq

p


def get_surface(tokens, with_spaces=False):
    surface = "".join(tokens).replace("-", "")
    return surface.replace("ﬁ", "fi")


def is_spacing_hyphenation(old_surface, new_surface):
    return old_surface == new_surface


TYPO_EDIT_DISTANCE = 3


def is_typographical(old_surface, new_surface):
    if edit_distance(old_surface, new_surface) < TYPO_EDIT_DISTANCE:
        if new_surface in words.words() and old_surface not in words.words():
            print(new_surface, old_surface)
            return True
        else:
            return False


def filter_diffs(filename):
    filtered_diffs = []
    with open(filename, 'r') as f:
        obj = json.load(f)
        for d in obj['diffs']:
            old_surface = get_surface(d['old'])
            new_surface = get_surface(d['new'])
            if not is_spacing_hyphenation(old_surface, new_surface):
                if is_typographical(old_surface, new_surface):
                    #print(d)
                    pass
                else:
                    filtered_diffs.append(d)
            #else:
            #    print(d)
        return filtered_diffs


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
        for forum in diffs_tried_forums:
            if not forum[f'{section}_status'] == 'complete':
                continue
            filenames = scc_lib.get_filenames(DATA_DIR, conference,
                                              forum['forum_id'])
            filtered_diffs = filter_diffs(filenames._asdict()[section])
            with open(filenames._asdict()[section], 'r') as f:
                obj = json.load(f)
                total += len(obj['diffs'])
            non_typos += len(filtered_diffs)
