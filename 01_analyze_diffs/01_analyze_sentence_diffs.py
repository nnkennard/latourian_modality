"""Categorize diffs according to type and scope
"""

import argparse
import collections
import json
import tqdm

import scc_lib

from nltk.metrics.distance import edit_distance
import pandas as pd

parser = argparse.ArgumentParser(description="")
parser.add_argument("-d", "--data_dir", type=str, help="Data dir")
parser.add_argument('-r',
                    '--record_directory',
                    default=('/work/pi_mccallum_umass_edu/nnayak_umass_edu/'
                             'latourian_modality/00_extract_data/records/'),
                    type=str)


def get_anchor_index(diff, sentence_ranges):
    for r in sentence_ranges:
        if diff['index'] in r:
            return r.start

def get_sentence(index, sentences):
    i = 0
    for sentence in sentences:
        if i <= index and index < i + len(sentence):
            return sentence
        i += len(sentence)

def source_to_dest_anchor(source_sentence_ranges, diffs, obj):
    source_sentence_starts = [r.start for r in source_sentence_ranges]
    dest_sentence_starts = list(source_sentence_starts)
    for d in diffs:
        offset = len(d['new']) - len(d['old'])
        for i, source_range in enumerate(source_sentence_ranges):
            if source_range.start > d['index']:
                dest_sentence_starts[i] += offset

    flat_source = sum(obj['tokens']['source'], [])
    flat_dest = sum(obj['tokens']['dest'], [])

    for a, b in zip(source_sentence_starts, dest_sentence_starts):
        print(flat_source[a], flat_dest[b])

    return {k:v for k, v in zip(source_sentence_starts, dest_sentence_starts)}




def get_sentence_diff_pairs(filename):
    with open(filename, 'r') as f:
        obj = json.load(f)

    source_sentence_ranges = scc_lib.compute_sentence_ranges(
        obj['tokens']['source'])

    source_to_dest = source_to_dest_anchor(source_sentence_ranges,
    obj['diffs'], obj)

    sentence_diff_list = []
    for diff in obj['diffs']:
        d_type, d_scope = scc_lib.get_diff_type_and_scope(
            diff, source_sentence_ranges)
        if (d_scope == scc_lib.DiffScope.IN_SENTENCE
                and not d_type == scc_lib.DiffType.TYPO):
            sentence_diff_list.append(diff)

    for sentence_diff in sentence_diff_list:
        anchor_index = get_anchor_index(sentence_diff, source_sentence_ranges)
        old_sentence = get_sentence(anchor_index, obj['tokens']['source'])
        new_sentence = get_sentence(source_to_dest[anchor_index],
                                    obj['tokens']['dest'])
        print(sentence_diff)
        print(" ".join(old_sentence))
        print(" ".join(new_sentence))
        print()


        #print(sentence_diff_list)

    return []


def main():
    args = parser.parse_args()

    sentence_diff_pairs = []

    for conference in scc_lib.Conference.ALL:
        diffs_tried_forums = scc_lib.get_records(args.record_directory,
                                                 conference,
                                                 scc_lib.Stage.COMPUTE,
                                                 full_records=True)
        for forum in diffs_tried_forums:
            filenames = scc_lib.get_filenames(args.data_dir, conference,
                                              forum['forum_id'])
            for section in ['abstract', 'intro']:
                if not forum[f'{section}_status'] == 'complete':
                    continue
                sentence_diff_pairs += get_sentence_diff_pairs(
                    filenames._asdict()[section])


if __name__ == "__main__":
    main()
