"""Extract abstract and introduction text from (truncated) OpenReview PDFs.
"""

import argparse
import collections
import glob
import json
import os
import re
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
parser.add_argument('-r',
                    '--record_directory',
                    default='./records/',
                    type=str,
                    help='prefix for tsv file with status of all forums')

VERSION_INFO_FIELDS = "title abstract intro debug_next_sec".split()
VersionInfo = collections.namedtuple("VersionInfo", VERSION_INFO_FIELDS)

PAPER_INFO_FIELDS = "conference forum_id initial_info final_info".split()
PaperInfo = collections.namedtuple("PaperInfo", PAPER_INFO_FIELDS)

ExtractionRecord = collections.namedtuple(
    "OpenReviewStatus", "status hint conference forum_id".split())

# =========== Extract text from PDF ===========================================


ERROR_PREFIX = "Error: Could not find 'pdftotext'"

def extract_text(pdf_path, metadata):
    # pdfdiff with only one command line argument simply extracts pdf text.
    output = subprocess.run(["python", "pdfdiff.py", pdf_path],
                            capture_output=True).stdout
    # TODO: check for errors

    output = output.decode()
    if output.startswith(ERROR_PREFIX):
        return ExtractionRecord(
            scc_lib.ExtractionStatus.PDF_PARSE_ERROR, output.replace("\n", " "), *metadata)
    else:
        return output


# =============================================================================


def subtitle_splitter(subtitle_strings, text, metadata):
    """Split text into before and after a subheading."""
    for subtitle in subtitle_strings:
        if subtitle in text:
            try:
                pre, post = text.split(subtitle, 1)
                return pre.strip(), post.strip()
            except ValueError:
                return ExtractionRecord(
                scc_lib.ExtractionStatus.TEXT_PARSE_ERROR, *metadata)


UNDER_REVIEW_RE = re.compile(
    r"Under review as a conference paper at ICLR 20[0-9]{2}\s?")
PUBLISHED_RE = re.compile(
    r"Published as a conference paper at ICLR 20[0-9]{2}\s?")


def remove_boilerplate(text):

    if UNDER_REVIEW_RE.match(text):
        boilerplate_re = UNDER_REVIEW_RE
        assert not PUBLISHED_RE.match(text)
    else:
        boilerplate_re = PUBLISHED_RE

    page_number = 1

    final_lines = []
    for line in text.split("\n"):
        if not line and final_lines:
            if final_lines[-1].endswith(str(page_number)):
                l = final_lines.pop(-1)
                final_lines.append(l[:-1])  # Max 3 pages in a pdf
                page_number += 1
        if boilerplate_re.match(line):
            final_lines.append(re.sub(boilerplate_re, "", line))
        elif line:
            final_lines.append(line)

    return "\n".join(final_lines)


PLACEHOLDER = "$$$$$$$$$$$$$"


def clean_hyphenation(text):

    return text.replace(  # clean up whitespace
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
    )


def parse_clean_text(text, metadata):
    # Text usually starts with the title in all caps.
    # Either the title is on its own line or the authors (either named or
    # anonymous) are on the same line after the title.
    maybe_title = text.split("\n")[0]
    if 'Anonymous' in maybe_title:  # Split before 'Anonymous'
        r = re.search("Anonymous", maybe_title).span()[0]
        title = maybe_title[:r]
    else:
        maybe_name_start = re.search("[A-Z][a-z]", maybe_title)
        if maybe_name_start is not None:  # A name-looking substring occurs
            title = maybe_title[:maybe_name_start.span()[0]]
        else:
            title = maybe_title  # Title occurs on its own line?

    # Most papers have either 'Abstract' or 'ABSTRACT' pretty reliably
    res = subtitle_splitter(["Abstract", "ABSTRACT"], text, metadata)
    if isinstance(res, scc_lib.ExtractionRecord):
        return res
    pre_abs, post_abs = res

    
    res = subtitle_splitter(
            ["1 Introduction", "1 INTRODUCTION"], post_abs, metadata)
    if isinstance(res, scc_lib.ExtractionRecord):
        return res

    abstract, post_int = res

    # Find the start of the second section in order to delimit the
    # introduction.
    next_sec_offset = re.search(r"2\s[A-Z]+", post_int).span()[0]
    introduction = post_int[:next_sec_offset]
    next_sec = post_int[next_sec_offset:next_sec_offset + 50]

    return VersionInfo(title, abstract, introduction, next_sec)



def process_pdf(pdf_path, metadata):
    maybe_text = extract_text(pdf_path, metadata)
    if isinstance(maybe_text, ExtractionRecord):
        return maybe_text

    if not maybe_text:
        dsds
    text = remove_boilerplate(maybe_text)
    text = clean_hyphenation(text)

    return parse_clean_text(text)

def main():
    args = parser.parse_args()

    for forum_id in scc_lib.get_completed_revisions_forums(
            args.status_directory, args.conference):

        print(forum_id)

        processed_texts = {}
        for version_name in [scc_lib.INITIAL, scc_lib.FINAL]:
            pdf_path = f"{args.data_dir}/{args.conference}/{forum_id}/{version_name}.pdf"
            maybe_processed_text = process_pdf(pdf_path,
                                               (args.conference, forum_id))
            if isinstance(maybe_processed_text, VersionInfo):
                processed_texts[stage] = maybe_processed_text

        print(processed_texts)

        if len(processed_texts) == 2:
            if processed_texts[scc_lib.INITIAL] == processed_texts[scc_lib.FINAL]:
                dsdsds
            with open(f'{args.data_dir}/{args.conference}/{forum_id}/texts.json',
            'w') as f:
                f.write(json.dumps(PaperInfo(args.conference, forum_id,
                    processed_texts[scc_lib.INITIAL]._asdict(),
                    processed_texts[scc_lib.FINAL]._asdict()
                              )._asdict(), indent=2))
            # write status
        else:
            # write error status
            pass


if __name__ == "__main__":
    main()
