import collections
import json

from nltk.metrics.distance import edit_distance


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
    COMPUTE = "compute"


def read_jsonl(filename):
    try:
        with open(filename, 'r') as f:
            return [json.loads(l) for l in f.readlines()]
    except FileNotFoundError:
        return []


# == Records helpers ==========================================================


def get_record_filename(record_directory, conference, data_stage):
    return f'{record_directory}/{data_stage}_record_{conference}.jsonl'


#def get_records(record_directory, conference, data_stage):
#    return read_jsonl(
#        get_record_filename(record_directory, conference, data_stage))

# == Helpers for resuming =====================================================


def get_records(record_directory,
                conference,
                stage,
                complete_only=False,
                full_records=False):
    records = read_jsonl(
        get_record_filename(record_directory, conference, stage))
    if complete_only:
        records = [r for r in records if r['status'] == 'complete']
    if full_records:
        return records
    else:
        return [r['forum_id'] for r in records]


def write_record(record, file_handle):
    file_handle.write(json.dumps(record._asdict()) + "\n")
    file_handle.flush()


# == Helpers for filenames ====================================================


class FileCategories(object):
    METADATA = "metadata"
    INITIAL = "initial"
    FINAL = "final"
    TEXTS = "texts"
    ABSTRACT = "abstract"
    INTRO = "intro"

    ALL = [METADATA, INITIAL, FINAL, TEXTS, ABSTRACT, INTRO]


LatmodFilenames = collections.namedtuple("LatmodFilenames", FileCategories.ALL)

FILENAMES = {
    FileCategories.METADATA: "metadata.json",
    FileCategories.INITIAL: "initial.pdf",
    FileCategories.FINAL: "final.pdf",
    FileCategories.TEXTS: "texts.json",
    FileCategories.ABSTRACT: "diffs_abstract.json",
    FileCategories.INTRO: "diffs_intro.json",
}


def get_filenames(data_directory, conference, forum):
    return LatmodFilenames(*[
        f'{data_directory}/{conference}/{forum}/{FILENAMES[filecat]}'
        for filecat in FileCategories.ALL
    ])


# == Categorizing diffs

TOKEN_DIFF_LENS = [
    (1, 2),  # One token added
    (1, 0),  # One token deleted
    (1, 1)  # One token changed
]
TYPO_EDIT_DISTANCE = 4


class DiffType(object):
    INSERT = "insert"
    DELETE = "delete"
    MODIFY = "modify"
    TYPO = "typo"


class DiffScope(object):
    TOKEN = "token"
    IN_SENTENCE = "in_sentence"
    MULTI_SENTENCE = "multi_sentence"


def compute_sentence_ranges(sentences):
    tokens_seen = 0
    sentence_ranges = []
    for sentence in sentences:
        end = tokens_seen + len(sentence)
        sentence_ranges.append(range(tokens_seen, end))
        tokens_seen = end

    return sentence_ranges


def get_diff_type(diff):
    if abs(edit_distance("".join(diff['old']),
                         "".join(diff['new']))) < TYPO_EDIT_DISTANCE:
        return DiffType.TYPO
    elif not diff['new']:
        return DiffType.DELETE
    elif len(diff['old']) == 1 and diff['old'] == diff['new'][:1]:
        return DiffType.INSERT
    else:
        return DiffType.MODIFY


def is_in_sentence(diff, sentence_ranges, skip_first=False):
    index = diff['index']
    if skip_first:
        index += 1
    if index == sentence_ranges[-1].stop:  # A sentence is being appended
        assert skip_first
        return True
    for r in sentence_ranges:
        if index in r:
            if index + len(diff['old']) in r:
                return True
            else:
                return False
    assert False


def get_diff_type_and_scope(diff, sentence_ranges):

    diff_type = get_diff_type(diff)

    scope = None
    diff_len = (len(diff['old']), len(diff['new']))
    if diff_len in TOKEN_DIFF_LENS:
        scope = DiffScope.TOKEN
    elif is_in_sentence(diff, sentence_ranges):
        scope = DiffScope.IN_SENTENCE
    else:
        if diff_type == DiffType.INSERT and is_in_sentence(
                diff, sentence_ranges, skip_first=True):
            scope = DiffScope.IN_SENTENCE
        else:
            scope = DiffScope.MULTI_SENTENCE
    assert scope is not None

    return diff_type, scope
