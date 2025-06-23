"""Use OpenReview API to get initial and final PDFs for ICLR submissions.
"""

import argparse
import collections
import json
import openreview
import os
import pikepdf
import tqdm

import scc_lib

parser = argparse.ArgumentParser(description='')
parser.add_argument('-d',
                    '--dir',
                    type=str,
                    help='directory to dump pdfs',
                    required=True)
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
                    help='saving outcomes of each stage')

# == OpenReview-specific stuff ===============================================


def export_signature(note):
    (signature, ) = note.signatures
    return signature.split("/")[-1]


class PDFStatus(object):
    # for paper revisions
    AVAILABLE = "available"
    DUPLICATE = "duplicate"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"


GUEST_CLIENT = openreview.Client(baseurl="https://api.openreview.net")

PDF_ERROR_STATUS_LOOKUP = {
    "ForbiddenError": PDFStatus.FORBIDDEN,
    "NotFoundError": PDFStatus.NOT_FOUND,
}

PDF_URL_PREFIX = "https://openreview.net/references/pdf?id="
FORUM_URL_PREFIX = "https://openreview.net/forum?id="

INVITATIONS = {
    f"iclr_{year}": f"ICLR.cc/{year}/Conference/-/Blind_Submission"
    for year in range(2018, 2025)
}


def is_review(note, conference):
    if conference == scc_lib.Conference.iclr_2023:
        return "Official_Review" in note.invitation
    elif conference == scc_lib.Conference.iclr_2022:
        return 'main_review' in note.content
    elif conference == scc_lib.Conference.iclr_2024:
        assert False
    else:
        return 'review' in note.content


OpenReviewRecord = collections.namedtuple(
    "OpenReviewStatus", "conference forum_id status decision".split())

# == Other helpers ===========================================================

Review = collections.namedtuple("Review",
                                "review_id text rating reviewer tcdate")


def first_not_none(l):
    for x in l:
        if x is not None:
            return x
    return None


# ============================================================================


def get_binary(note):
    try:  # try to get the PDF for this paper revision
        pdf_binary = GUEST_CLIENT.get_pdf(note.id, is_reference=True)
        pdf_status = PDFStatus.AVAILABLE
    except openreview.OpenReviewException as e:
        pdf_status = PDF_ERROR_STATUS_LOOKUP[e.args[0]["name"]]
        pdf_binary = None
    return pdf_status, pdf_binary


def write_pdfs(forum_dir, initial_binary, final_binary):
    for binary, version in [(initial_binary, scc_lib.INITIAL),
                            (final_binary, scc_lib.FINAL)]:
        assert binary is not None
        full_pdf_path = f'{forum_dir}/{version}_full.pdf'
        pdf_path = f'{forum_dir}/{version}.pdf'
        with open(full_pdf_path, "wb") as f:
            f.write(binary)
        full_pdf = pikepdf.Pdf.open(full_pdf_path)
        truncated_pdf = pikepdf.Pdf.new()
        for page_num in range(3):
            try:
                truncated_pdf.pages.append(full_pdf.pages[page_num])
            except IndexError:
                break  # Sometimes there are fewer than 3 pages
        truncated_pdf.save(pdf_path)
        os.remove(full_pdf_path)


def get_last_valid_reference(references):
    for r in reversed(references):
        status, binary = get_binary(r)
        if status == PDFStatus.AVAILABLE:
            return (r, binary)
    return None, None


def get_review_text_and_rating(note, conference):
    """Get raw review text. Review text field differs between years.
    """
    if conference == scc_lib.Conference.iclr_2023:
        review_text = "\n".join([
            note.content[key] for key in [
                "summary_of_the_paper",
                "strength_and_weaknesses",
                "clarity,_quality,_novelty_and_reproducibility",
            ]
        ])
        rating = note.content['recommendation']
    elif conference == scc_lib.Conference.iclr_2022:
        review_text = note.content['main_review']
        rating = note.content['recommendation']
    elif conference == scc_lib.Conference.iclr_2024:
        assert False
    else:
        review_text = note.content['review']
        rating = note.content['rating']

    return review_text, rating


def write_metadata(forum_dir, forum, conference, initial_id, final_id,
                   decision, review_notes):
    reviews = []
    for review_note in review_notes:
        review_text, rating = get_review_text_and_rating(
            review_note, conference)
        reviews.append(
            Review(review_note.id, review_text, rating,
                   export_signature(review_note),
                   review_note.tcdate)._asdict())
    with open(f'{forum_dir}/metadata.json', 'w') as f:
        f.write(
            json.dumps(
                {
                    'identifier': forum.id,
                    'reviews': reviews,
                    'decision': decision,
                    'conference': conference,
                    'urls': {
                        'forum': f'{FORUM_URL_PREFIX}{forum.id}',
                        'initial': f'{PDF_URL_PREFIX}{initial_id}',
                        'final': f'{PDF_URL_PREFIX}{final_id}',
                    }
                },
                indent=2))


def process_forum(forum, conference, output_dir):

    # === Get all notes, reviews, decisions, etc ==============================

    forum_notes = GUEST_CLIENT.get_all_notes(forum=forum.id)

    # Retrieve all reviews from the forum
    review_notes = [
        note for note in forum_notes if is_review(note, conference)
    ]
    # The conditions that make a note a review differ from year to year.

    # Retrieve decision
    decision = first_not_none([
        note.content.get('decision', note.content.get('recommendation', None))
        for note in forum_notes
    ])
    if decision is None:
        return scc_lib.DownloadStatus.NO_DECISION, "None"

    # e.g. If the paper was withdrawn
    if not review_notes:
        return scc_lib.DownloadStatus.NO_REVIEWS, decision

    # === Get `initial' and `final' pdfs ======================================

    # Retrieve all revisions of the manuscript in order of submission
    references = sorted(GUEST_CLIENT.get_all_references(referent=forum.id,
                                                        original=True),
                        key=lambda x: x.tcdate)

    # Valid references are those associated with a valid PDF.

    # --- final submission ----------------------------------------------------
    # The latest valid revision

    # The 'final' version is the latest valid version
    final_reference, final_binary = get_last_valid_reference(references)

    # --- initial submission --------------------------------------------------
    # The latest valid pre-review revision

    # Creation time of first review:
    # Changes made before this time cannot have been influenced by reviewers.
    first_review_time = min(rev.tcdate for rev in review_notes)

    references_before_review = [
        r for r in references if r.tcdate <= first_review_time
    ]
    # The initial revision is the latest valid revision of the list above
    initial_reference, initial_binary = get_last_valid_reference(
        references_before_review)

    # === Finalize ============================================================

    # Proceed only for forums with valid and distinct initial and final
    # versions
    if final_reference is not None and initial_reference is not None:
        if not final_reference.id == initial_reference.id:

            # Create subdirectory
            forum_dir = f'{output_dir}/{forum.id}'
            os.makedirs(forum_dir, exist_ok=True)

            # Write pdfs and metadata
            write_pdfs(forum_dir, initial_binary, final_binary)
            write_metadata(forum_dir, forum, conference, initial_reference.id,
                           final_reference.id, decision, review_notes)

            return scc_lib.DownloadStatus.COMPLETE, decision
        else:
            # Manuscript was not revised after the first review
            return scc_lib.DownloadStatus.NO_REVISION, decision
    else:
        # No versions associated with valid PDFs were found
        return scc_lib.DownloadStatus.NO_PDF, decision


def main():

    args = parser.parse_args()

    # A directory will be made for each paper submission under the output directory.
    final_dir = f'{args.dir}/{args.conference}/'
    os.makedirs(final_dir, exist_ok=True)

    # Gets top level notes for each `forum' (each paper submission is assigned
    # a forum)
    forum_notes = GUEST_CLIENT.get_all_notes(
        invitation=INVITATIONS[args.conference])

    downloads_already_done = scc_lib.get_records(args.record_directory,
    args.conference, scc_lib.Stage.DOWNLOAD)
    #processed_forums = scc_lib.get_downloads_processed_forums(
    #    args.record_directory, args.conference)

    with open(
            scc_lib.get_record_filename(args.record_directory, args.conference,
                                        scc_lib.Stage.DOWNLOAD), 'a') as f:
        for forum in tqdm.tqdm(forum_notes):
            if forum.id in downloads_already_done:
                continue

            # Process a forum. As a side effect, write pdfs to directory.
            status, decision = process_forum(forum, args.conference, final_dir)
            f.write(
                json.dumps(
                    OpenReviewRecord(args.conference, forum.id, status,
                                     decision)._asdict()) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
