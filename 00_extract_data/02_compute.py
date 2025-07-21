"""Extract abstract and introduction text from (truncated) OpenReview PDFs.
"""

import argparse
import collections
import json
import os
import re
import tqdm
import subprocess
import stanza

import scc_lib
import scc_diff_lib

parser = argparse.ArgumentParser(description="")
parser.add_argument(
    "-d",
    "--data_dir",
    type=str,
    help="Data dir",
)
parser.add_argument("-c",
                    "--conference",
                    type=str,
                    choices=scc_lib.Conference.ALL,
                    help="conference_year, e.g. iclr_2022",
                    required=True)
parser.add_argument('-r',
                    '--record_directory',
                    default='./records/',
                    type=str,
                    help='prefix for tsv file with status of all forums')

DiffingRecord = collections.namedtuple(
    "DiffingRecord", "conference forum_id part source dest status".split())

SENTENCIZE_PIPELINE = stanza.Pipeline("en", processors="tokenize")


def get_tokens(text):
    return list([t.to_dict()[0]['text'] for t in s.tokens]
                for s in SENTENCIZE_PIPELINE(text).sentences)


def main():
    args = parser.parse_args()

    diffs_already_done = scc_lib.get_records(args.record_directory,
                                             args.conference,
                                             scc_lib.Stage.COMPUTE)

    possible_pairs = [
        (scc_lib.SUBMITTED, scc_lib.DISCUSSED),
        (scc_lib.DISCUSSED, scc_lib.FINAL),
        (scc_lib.SUBMITTED, scc_lib.FINAL),
    ]

    with open(
            scc_lib.get_record_filename(args.record_directory, args.conference,
                                        scc_lib.Stage.COMPUTE), 'a') as f:

        for forum_id in tqdm.tqdm(
                scc_lib.get_records(args.record_directory,
                                    args.conference,
                                    scc_lib.Stage.EXTRACT,
                                    complete_only=True)):

            if forum_id in diffs_already_done:
                continue

            texts_filename = f'{args.data_dir}/{args.conference}/{forum_id}/texts.json'
            with open(texts_filename, 'r') as g:
                obj = json.load(g)

                pairs_to_diff = []
                for source, dest in possible_pairs:
                    if obj[source] is not None and obj[dest] is not None:
                        pairs_to_diff.append((source, dest))

                for source, dest in pairs_to_diff:
                    key = f'{source}_{dest}'
                    for part in ['abstract', 'intro']:
                        filename = texts_filename.replace(
                            'texts', f'diffs_{part}_{key}')
                        d = scc_diff_lib.DocumentDiff(get_tokens(obj[source][part]),
                                                      get_tokens(obj[dest][part]))
                        if d.error is None:
                            result = "complete"
                            with open(filename, 'w') as h:
                                h.write(d.dump())
                        else:
                            result = d.error
                        scc_lib.write_record(
                            DiffingRecord(args.conference, forum_id, part,
                                          source, dest, result), f)


if __name__ == "__main__":
    main()
