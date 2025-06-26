"""Categorize diffs according to type and scope
"""

import argparse
import collections
import json
import tqdm

import scc_lib

import pandas as pd

parser = argparse.ArgumentParser(description="")
parser.add_argument("-d", "--data_dir", type=str, help="Data dir")
parser.add_argument('-r',
                    '--record_directory',
                    default=('/work/pi_mccallum_umass_edu/nnayak_umass_edu/'
                             'latourian_modality/00_extract_data/records/'),
                    type=str)


def count_categories(filename):
    with open(filename, 'r') as f:
        obj = json.load(f)

    sentence_ranges = scc_lib.compute_sentence_ranges(obj['tokens']['source'])
    return collections.Counter([
        scc_lib.get_diff_type_and_scope(d, sentence_ranges)
        for d in obj['diffs']
    ])


def main():
    args = parser.parse_args()

    rows = []

    for conference in scc_lib.Conference.ALL:
        diffs_tried_forums = scc_lib.get_records(args.record_directory,
                                                 conference,
                                                 scc_lib.Stage.COMPUTE,
                                                 full_records=True)

        diff_categories = collections.Counter()

        print(conference)
        for section in ['abstract', 'intro']:
            print("  " + section)

            for forum in diffs_tried_forums:
                if not forum[f'{section}_status'] == 'complete':
                    continue
                filenames = scc_lib.get_filenames(args.data_dir, conference,
                                                  forum['forum_id'])
                diff_categories += count_categories(
                    filenames._asdict()[section])
                #if section == 'abstract':
                #    diff_categories += count_categories(filenames.abstract)
                #else:
                #    diff_categories += count_categories(filenames.intro)

            for (d_type, d_scope), count in diff_categories.items():
                rows.append({
                    "conference": conference,
                    "section": section,
                    "d_type": d_type,
                    "d_scope": d_scope,
                    "count": count
                })
    pd.DataFrame.from_dict(rows).to_csv('temp_counts.csv')


if __name__ == "__main__":
    main()
