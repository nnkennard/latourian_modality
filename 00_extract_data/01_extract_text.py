"""Extract abstract and introduction text from (truncated) OpenReview PDFs.
"""

import argparse
import collections
import glob
import os
import tqdm
import subprocess

import scc_lib

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
parser.add_argument('-s',
                    '--status_directory',
                    default='./statuses/',
                    type=str,
                    help='prefix for tsv file with status of all forums')

PLACEHOLDER = "$$$$$$$$$$$$$"

ERROR_PREFIX = "Error: Could not find 'pdftotext'"


class TextExtractionStatus(object):
    COMPLETE = "complete"
    PDFTOTEXT_ERROR = "pdftotext_error"


TextExtractionStatusRecord = collections.namedtuple(
    "TextExtractionStatusRecord",
    "status error_hint conference forum_id".split())


def get_completed_pdfs(pdf_glob):
    txt_glob = pdf_glob.replace('.pdf', '.txt')
    return list(glob.glob(txt_glob))


def extract_text(pdf_path, metadata):
    # pdfdiff with only one command line argument simply extracts pdf text.
    output = subprocess.run(["python", "pdfdiff.py", pdf_path],
                            capture_output=True).stdout
    # TODO: check for errors

    output = output.decode()
    if output.startswith(ERROR_PREFIX):
        metadata.update({
            'status': TextExtractionStatus.PDFTOTEXT_ERROR,
            'error_hint': output
        })
        return TextExtractionStatusRecord(
            TextExtractionStatusRecord.PDFTOTEXT_ERROR, output, *metadata)
    else:
        return output


"""
    return (output.replace(  # clean up whitespace
        "-\n",
        ""  # remove hyphenations
    ).replace(
        "\n\n",
        PLACEHOLDER  # placeholder for real newlines
    ).replace(
        "\n",
        " "  # remove line breaks
    ).replace(
        PLACEHOLDER,
        "\n\n"  # restore real newlines
    ))
"""


def main():
    args = parser.parse_args()

    pdf_glob = f"{args.data_dir}/{args.conference}/*/*.pdf"
    completed_txts = get_completed_pdfs(pdf_glob)

    for pdf_path in tqdm.tqdm(list(glob.glob(pdf_glob))):

        output_path = pdf_path.replace('.pdf', '.txt')
        if output_path in completed_txts:
            continue

        with open(output_path, 'w') as f:
            result = extract_text(pdf_path)
            if isinstance(result, str):
                result = process_text(maybe_text)
                if isinstance(result,  
            assert isinstance(maybe_text, TextExtractionStatusRecord)


if __name__ == "__main__":
    main()
