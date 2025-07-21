import collections
import glob
import gzip
import tqdm

YEAR_CUTOFF = 1980


def main():

    UNIGRAM_PATH = "/gypsum/work1/mccallum/nnayak/google_unigrams/"
    with open('counts.txt', 'w') as g:
        for filename in tqdm.tqdm(
                sorted(list(glob.glob(f'{UNIGRAM_PATH}*.gz')))):
            counts = collections.Counter()
            with gzip.open(filename, 'rb') as f:
                for line in f:
                    token, year, count, _ = line.split(b"\t")
                    if not token.strip():
                        continue
                    if int(year) >= YEAR_CUTOFF:
                        counts[token.decode().lower()] += int(count)

            for token, count in counts.most_common():
                if count < 100:
                    break
                g.write(f'{token}\t{count}\n')


if __name__ == "__main__":
    main()
