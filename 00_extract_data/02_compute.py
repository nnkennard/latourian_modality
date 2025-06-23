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
    "DiffingRecord", "conference forum_id abstract_status intro_status".split())

SENTENCIZE_PIPELINE = stanza.Pipeline("en", processors="tokenize")


def get_tokens(text):
    return list([t.to_dict()[0]['text'] for t in s.tokens]
                for s in SENTENCIZE_PIPELINE(text).sentences)


def main():
    args = parser.parse_args()

    diffs_already_done = scc_lib.get_records(
        args.record_directory, args.conference, scc_lib.Stage.COMPUTE)

    with open(
            scc_lib.get_record_filename(args.record_directory, args.conference,
                                        scc_lib.Stage.COMPUTE), 'a') as f:

        for forum_id in tqdm.tqdm(scc_lib.get_records(
                args.record_directory, args.conference, scc_lib.Stage.EXTRACT,
                complete_only=True)):

            if forum_id in diffs_already_done:
                continue

            result_by_part = {}
            texts_filename = f'{args.data_dir}/{args.conference}/{forum_id}/texts.json'
            with open(texts_filename, 'r') as g:
                obj = json.load(g)
                for part in ['abstract', 'intro']:
                    d = scc_diff_lib.DocumentDiff(
                        get_tokens(obj['initial_info'][part]),
                        get_tokens(obj['final_info'][part]))
                    if d.error is None:
                        result_by_part[part] = "complete"
                        with open(
                                texts_filename.replace('texts',
                                                       f'diffs_{part}'),
                                'w') as h:
                            h.write(d.dump())
                    else:
                        result_by_part[part] = d.error

                scc_lib.write_record(DiffingRecord(args.conference, forum_id,
                        result_by_part['abstract'],
                        result_by_part['intro']), f)

if __name__ == "__main__":
    main()
