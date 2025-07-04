import glob
import gzip
import pickle
import tqdm


class TrieNode(object):

    def __init__(self):
        self.children = {}
        self.is_terminal = False
        self.count = 0

    def add(self, seq, count):

        if not seq:
            self.is_terminal = True
            self.count += count
        else:
            first = seq.pop(0)
            if first not in self.children:
                self.children[first] = TrieNode()
            self.children[first].add(seq, count)

    def find(self, token):
        if not token:
            if self.is_terminal:
                return True, self.count
            else:
                return False, None

        first = token.pop(0)
        if first not in self.children:
            return False, None
        else:
            return self.children[first].find(token)


class CountTrie(object):

    def __init__(self):
        self.root = TrieNode()

    def insert(self, token, count):
        self.root.add(list(token), count)

    def find(self, token):
        return self.root.find(list(token.lower()))


YEAR_CUTOFF = 1980


def main():

    trie = CountTrie()
    UNIGRAM_PATH = "/gypsum/work1/mccallum/nnayak/google_unigrams/"
    for filename in tqdm.tqdm(glob.glob(f'{UNIGRAM_PATH}*')):
        with gzip.open(filename, 'rb') as f:
            for line in f:
                token, year, count, _ = line.split(b"\t")
                if int(year) >= YEAR_CUTOFF:
                    trie.insert(token.decode().lower(), int(count))

    with open('spellcheck.pkl', 'wb') as f:
        pickle.dump(trie, f)


if __name__ == "__main__":
    main()
