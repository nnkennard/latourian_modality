"""Wrappers around Myers diff and difflib for use in scientific coconstruction.

Since source and destination sequence lengths (n and d respectively), can be
quite high, O(nd) runtime of Myers is prohibitively high. Also, since diffs can
be very localized, there are large unchanged subsequences.

We first use get_matching_blocks from difflib (Python library) to find maximal
unchanged subsequences. We invert this list to find non-matching blocks, then
use Myers to describe the edirs within the non-matching blocks.
"""

import collections
import difflib
import interval
import json
import myers
import re
import sys
import tqdm

MATCHING_BLOCK = "MatchingBlock"
NONMATCHING_BLOCK = "NonMatchingBlock"
MAX_LEN = 3000

MatchingBlock = collections.namedtuple(MATCHING_BLOCK, "a b l".split())
NonMatchingBlock = collections.namedtuple(NONMATCHING_BLOCK,
                                          "a b l_a l_b".split())
#Diff = collections.namedtuple("Diff",
#    "index old_tokens new_tokens".split())

Diff2 = collections.namedtuple(
    "Diff2", "old_index new_index old_tokens new_tokens".split())


def flatten_sentences(sentences):
    return sum(sentences, [])


def compute_ranges(unflat_sentences):
    cursor = 0
    ranges = []
    for sent in unflat_sentences:
        end = cursor + len(sent)
        ranges.append(interval.Interval(cursor, end))
        cursor = end
    return ranges


EMPTY_INTERVAL = interval.Interval(0, 0)


def sentence_split(anchor, tokens, ranges, original_tokens):
    target_range = interval.Interval(anchor + 1, anchor + 1 + len(tokens))
    diff_ranges = []
    for r in ranges:
        if r == target_range:
            diff_ranges.append(r)
        else:
            maybe_intersection = r & target_range
            if maybe_intersection == EMPTY_INTERVAL:
                continue
            diff_ranges.append(maybe_intersection)
    split_tokens = []
    for r in diff_ranges:
        split_tokens.append(original_tokens[r.lower_bound:r.upper_bound])

    assert sum(split_tokens, []) == tokens
    return split_tokens


class DocumentDiff(object):

    def __init__(self, unflat_source_tokens, unflat_dest_tokens):
        # Saving these, but they are only used for output
        self.source_unflat = unflat_source_tokens
        self.dest_unflat = unflat_dest_tokens

        self.source_ranges = compute_ranges(self.source_unflat)
        self.dest_ranges = compute_ranges(self.dest_unflat)

        self.source_tokens = flatten_sentences(unflat_source_tokens)
        self.dest_tokens = flatten_sentences(unflat_dest_tokens)

        self.error = None
        self.calculate()

    def calculate(self):

        # Get matching and nonmatching blocks, then verify block calculation
        blocks = self._get_matching_blocks()

        # Verify block calculation
        self._reconstruct_from_blocks(blocks)

        # Blocks to chunk diffs
        chunk_diffs = []
        for block in blocks:
            if isinstance(block, NonMatchingBlock):
                chunk_diffs += self._block_to_chunk_diffs(block)

        # Verify chunk diff calculations
        self._reconstruct_from_chunk_diffs(chunk_diffs)

        #self.diffs = chunk_diffs
        self.diffs = []
        for chunk_diff in chunk_diffs:
            self.diffs.append(self._unchunk_chunk_diff(chunk_diff))

        # Verify chunk diff calculations
        self._reconstruct_from_diffs()

    def _get_matching_blocks(self):
        """Get maximal matching blocks and calculate nonmatching blocks.
        """
        matching_blocks = difflib.SequenceMatcher(
            None, self.source_tokens, self.dest_tokens).get_matching_blocks()

        blocks = []  # Alternating matching and nonmatching blocks

        # Special treatment for first block
        first_matching_block = matching_blocks[0]

        if first_matching_block[:2] != (0, 0):
            # The pair does not start with a matching block, add a
            # NonMatchingBlock
            source_cursor, dest_cursor = first_matching_block[:2]
            blocks.append(NonMatchingBlock(0, 0, source_cursor, dest_cursor))

        for prev, curr in zip(matching_blocks[:-1], matching_blocks[1:]):
            # Just add in the matching block
            blocks.append(MatchingBlock(*prev))

            # Find the edges of the nonmatching block.
            # Where the previous matching block ends
            source_cursor = prev.a + prev.size
            dest_cursor = prev.b + prev.size
            # Where the next matching block starts
            source_nonmatching_len = curr.a - source_cursor
            dest_nonmatching_len = curr.b - dest_cursor
            blocks.append(
                NonMatchingBlock(source_cursor, dest_cursor,
                                 source_nonmatching_len, dest_nonmatching_len))

        final_blocks = []

        return blocks

    def _block_to_chunk_diffs(self, block):
        """Convert nonmatching block into a diff."""

        if block.l_b + block.l_a > MAX_LEN:
            print(f"Skipped large block")
            # This diff adds many characters. It's likely to be something like
            # an appendix being added. We just convert the block into one large
            # diff.
            return [
                Diff2(block.a - 1, block.b - 1,
                      self.source_tokens[block.a:block.a + block.l_a],
                      self.dest_tokens[block.b:block.b + block.l_b])
            ]

        myers_diff = myers.diff(
            self.source_tokens[block.a:block.a + block.l_a],
            self.dest_tokens[block.b:block.b + block.l_b])

        # In our method of diff naming, each diff needs to be anchored to an
        # index in the source sequence. The anchors are collected below.
        indexed_myers_diff = []
        original_index = block.a - 1
        dest_index = block.b - 1
        for action, token in myers_diff:
            indexed_myers_diff.append(
                (original_index, dest_index, action, token))
            assert action in 'kir'
            if action in 'kr':
                original_index += 1
            if action in 'ki':
                dest_index += 1

        diffs = []
        diff_str = "".join(x[0] for x in myers_diff)

        for m in re.finditer("([ir]+)", diff_str):
            # A sequence of non-keep actions (inserts and removes)
            start, end = m.span()
            diff_substr = diff_str[start:end]
            diff_source_anchor, diff_dest_anchor, _, _ = indexed_myers_diff[
                start]

            inserted = []
            removed = []

            for i in range(start, end):
                action, token = myers_diff[i]
                if action == 'i':
                    inserted.append(token)
                else:
                    removed.append(token)

            diffs.append(
                Diff2(diff_source_anchor, diff_dest_anchor, removed, inserted))
        return diffs

    def _unchunk_chunk_diff(self, chunk_diff):
        unchunked_old = sentence_split(chunk_diff.old_index,
                                       chunk_diff.old_tokens,
                                       self.source_ranges, self.source_tokens)
        unchunked_new = sentence_split(chunk_diff.new_index,
                                       chunk_diff.new_tokens, self.dest_ranges,
                                       self.dest_tokens)
        return Diff2(chunk_diff.old_index, chunk_diff.new_index, unchunked_old,
                     unchunked_new)

    def dump(self):
        if self.error is None:
            return json.dumps(
                {
                    "tokens": {
                        "source": self.source_unflat,
                        "dest": self.dest_unflat
                    },
                    "diffs": [d._asdict() for d in self.diffs]
                },
                indent=2)
        else:
            return ""

    # ======= Reconstruction methods below ====================================
    # These methods are used to check for bugs in the diff logic.

    def _reconstruct_from_blocks(self, blocks):
        reconstructed_tokens = []
        for block in blocks:
            if isinstance(block, MatchingBlock):
                reconstructed_tokens += self.source_tokens[block.a:block.a +
                                                           block.l]
            else:
                assert isinstance(block, NonMatchingBlock)
                if block.l_b:
                    reconstructed_tokens += self.dest_tokens[block.b:block.b +
                                                             block.l_b]

        assert reconstructed_tokens == self.dest_tokens

    def _reconstruct_from_chunk_diffs(self, chunk_diffs):
        reconstructed_tokens = []
        source_cursor = 0
        for i, diff in enumerate(chunk_diffs):
            reconstructed_tokens += self.source_tokens[source_cursor:diff.
                                                       old_index + 1]
            reconstructed_tokens += diff.new_tokens
            source_cursor = diff.old_index + 1 + len(diff.old_tokens)

            assert ((diff.old_index == diff.new_index == -1)
                    or self.source_tokens[diff.old_index]
                    == self.dest_tokens[diff.new_index])

        reconstructed_tokens += self.source_tokens[source_cursor:]

        if not reconstructed_tokens == self.dest_tokens:
            self.error = "chunk_reconstruction_error"

    def _reconstruct_from_diffs(self):
        reconstructed_tokens = []
        source_cursor = 0
        for i, diff in enumerate(self.diffs):
            reconstructed_tokens += self.source_tokens[source_cursor:diff.
                                                       old_index + 1]
            for new_string in diff.new_tokens:
                reconstructed_tokens += new_string

            source_cursor = diff.old_index + 1
            for old_string in diff.old_tokens:
                source_cursor += len(old_string)

        reconstructed_tokens += self.source_tokens[source_cursor:]

        if not reconstructed_tokens == self.dest_tokens:
            self.error = "reconstruction_error"
