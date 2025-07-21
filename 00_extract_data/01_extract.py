"""Extract abstract and introduction text from (truncated) OpenReview PDFs.
"""

import argparse
import collections
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

VERSION_FIELDS = "title abstract intro debug_next_sec".split()
Version = collections.namedtuple("Version", VERSION_FIELDS)

PAPER_FIELDS = "conference forum_id submitted discussed final".split()
Paper = collections.namedtuple("Paper", PAPER_FIELDS)

ExtractionRecord = collections.namedtuple(
    "ExtractionRecord", "conference forum_id status details".split())

# =========== Extract text from PDF ===========================================

ERROR_PREFIX = "Error: Could not find 'pdftotext'"


def extract_text(pdf_path):
    # pdfdiff with only one command line argument simply extracts pdf text.
    output = subprocess.run(["python", "pdfdiff.py", pdf_path],
                            capture_output=True).stdout
    output = output.decode()
    if output.startswith(ERROR_PREFIX):
        return None
    else:
        return output


# =============================================================================

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


def subtitle_splitter(subtitle_strings, text):
    """Split text into before and after a subheading."""
    for subtitle in subtitle_strings:
        if subtitle in text:
            try:
                pre, post = text.split(subtitle, 1)
                return pre.strip(), post.strip()
            except ValueError:
                return scc_lib.ExtractionStatus.TEXT_PARSE_ERROR
    return scc_lib.ExtractionStatus.TEXT_PARSE_ERROR


def parse_clean_text(text):
    # Text usually starts with the title in all caps.
    # Either the title is on its own line or the authors (either named or
    # anonymous) are on the same line after the title.
    maybe_title = text.split("\n")[0]
    if 'Anonymous' in maybe_title:  # Split before 'Anonymous'
        title = maybe_title[:re.search("Anonymous", maybe_title).span()[0]]
    else:
        maybe_name_start = re.search("[A-Z][a-z]", maybe_title)
        if maybe_name_start is not None:  # A name-looking substring occurs
            title = maybe_title[:maybe_name_start.span()[0]]
        else:
            title = maybe_title  # Title occurs on its own line?

    # Most papers have either 'Abstract' or 'ABSTRACT' pretty reliably
    result = subtitle_splitter(["Abstract", "ABSTRACT"], text)
    if isinstance(result, str):  # It's an error code
        return result
    else:
        _, post_abs = result

    result = subtitle_splitter(["1 Introduction", "1 INTRODUCTION"], post_abs)
    if isinstance(result, str):  # It's an error code
        return result
    else:
        abstract, post_intro = result

    # Find the start of the second section in order to delimit the
    # introduction.
    maybe_next_sec_offset = re.search(r"2\s[A-Z][A-Z]+", post_intro)
    if maybe_next_sec_offset is None:
        return scc_lib.ExtractionStatus.TEXT_PARSE_ERROR
    else:
        next_sec_offset = maybe_next_sec_offset.span()[0]

    introduction = post_intro[:next_sec_offset]
    next_sec = post_intro[next_sec_offset:next_sec_offset + 50]

    return Version(title, abstract, introduction, next_sec)


def process_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    maybe_text = extract_text(pdf_path)
    if maybe_text is None:
        return scc_lib.ExtractionStatus.PDF_PARSE_ERROR
    elif not maybe_text:
        return scc_lib.ExtractionStatus.EMPTY_PDF
    else:
        return parse_clean_text(
            clean_hyphenation(remove_boilerplate(maybe_text)))


def main():
    args = parser.parse_args()

    extraction_already_done = scc_lib.get_records(args.record_directory,
                                                  args.conference,
                                                  scc_lib.Stage.EXTRACT)

    with open(
            scc_lib.get_record_filename(args.record_directory, args.conference,
                                        scc_lib.Stage.EXTRACT), 'a') as f:

        for forum_id in tqdm.tqdm(
                scc_lib.get_records(args.record_directory,
                                    args.conference,
                                    scc_lib.Stage.DOWNLOAD,
                                    complete_only=True)):

            if forum_id in extraction_already_done:
                continue

            processed_texts = {}
            for version_name in scc_lib.VERSIONS:
                pdf_path = f"{args.data_dir}/{args.conference}/{forum_id}/{version_name}.pdf"
                maybe_processed_pdf = process_pdf(pdf_path)
                if maybe_processed_pdf is not None:
                    processed_texts[version_name] = maybe_processed_pdf

            valid_versions = [
                v for v in processed_texts.values() if isinstance(v, Version)
            ]
            errors = [
                e for e in processed_texts.values() if isinstance(e, str)
            ]
            if len(valid_versions) < 2:
                if not errors:
                    record = ExtractionRecord(
                        args.conference, forum_id,
                        scc_lib.ExtractionStatus.NO_CHANGE, None)
                else:
                    details = []
                    for version_name, maybe_error in processed_texts.items():
                        if isinstance(maybe_error, str):
                            details.append(f'{version_name}_{maybe_error}')
                    record = ExtractionRecord(args.conference, forum_id,
                                              scc_lib.ExtractionStatus.ERROR,
                                              "|".join(details))
            else:
                # At least 2 versions -- some diffs to look at
                prepared_processed_texts = {}
                details = []
                for version_name, maybe_version in processed_texts.items():
                    if maybe_version is None:
                        prepared_processed_texts[version_name] = None
                    elif isinstance(maybe_version, str):
                        details.append(f'{version_name}_{maybe_error}')
                        prepared_processed_texts[version_name] = None
                    else:
                        prepared_processed_texts[
                            version_name] = maybe_version._asdict()
                paper = Paper(
                    args.conference,
                    forum_id,
                    prepared_processed_texts.get(scc_lib.SUBMITTED, None),
                    prepared_processed_texts.get(scc_lib.DISCUSSED, None),
                    prepared_processed_texts.get(scc_lib.FINAL, None),
                )
                with open(
                        f'{args.data_dir}/{args.conference}/{forum_id}/texts.json',
                        'w') as g:
                    g.write(json.dumps(paper._asdict(), indent=2))
                if details:
                    details = "|".join(details)
                    record = ExtractionRecord(args.conference, forum_id,
                                          scc_lib.ExtractionStatus.ERROR,
                                          details)
                else:
                    details = None
                    record = ExtractionRecord(args.conference, forum_id,
                                          scc_lib.ExtractionStatus.COMPLETE,
                                          details)

                scc_lib.write_record(record, f)


if __name__ == "__main__":
    main()
