import json


class Conference(object):
    iclr_2018 = "iclr_2018"
    iclr_2019 = "iclr_2019"
    iclr_2020 = "iclr_2020"
    iclr_2021 = "iclr_2021"
    iclr_2022 = "iclr_2022"
    iclr_2023 = "iclr_2023"
    iclr_2024 = "iclr_2024"
    ALL = [
        iclr_2018,
        iclr_2019,
        iclr_2020,
        iclr_2021,
        iclr_2022,
        iclr_2023,
    ]


# Version names
INITIAL, FINAL = "initial final".split()


class DownloadStatus(object):
    COMPLETE = "complete"
    NO_REVIEWS = "no_reviews"
    NO_PDF = "no_pdf"
    NO_REVISION = "no_revision"
    NO_DECISION = "no_decision"


class ExtractionStatus(object):
    COMPLETE = "complete"
    EMPTY_PDF = "empty_pdf"
    PDF_PARSE_ERROR = "pdf_parse_error"
    TEXT_PARSE_ERROR = "text_parse_error"
    NO_CHANGE = "no_change"
    ERROR = "error"


class Stage(object):
    DOWNLOAD = "download"
    EXTRACT = "extract"


def read_jsonl(filename):
    try:
        with open(filename, 'r') as f:
            return [json.loads(l) for l in f.readlines()]
    except FileNotFoundError:
        return []


def get_record_filename(record_directory, conference, data_stage):
    return f'{record_directory}/{data_stage}_record_{conference}.jsonl'


def get_records(record_directory, conference, data_stage):
    return read_jsonl(
        get_record_filename(record_directory, conference, data_stage))


def get_extraction_processed_forums(record_directory, conference):
    return [
        r['forum_id']
        for r in get_records(record_directory, conference, Stage.EXTRACT)
    ]

def get_downloads_processed_forums(record_directory, conference):
    return [
        r['forum_id']
        for r in get_records(record_directory, conference, Stage.DOWNLOAD)
    ]


def get_completed_revisions_forums(record_directory, conference):
    return [
        r['forum_id']
        for r in get_records(record_directory, conference, Stage.DOWNLOAD)
        if r['status'] == DownloadStatus.COMPLETE
    ]
