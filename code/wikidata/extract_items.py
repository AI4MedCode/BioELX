import os
import gzip
import time
from pathlib import Path
import pandas as pd
from tqdm.auto import tqdm
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from common.constants import DATA_DIR

def parse_mysql_tuples(values_str: str):
    """
    Parse the "(...),(...)" part of a MySQL INSERT statement.
    Handles quoted strings with backslash escapes.
    Yields rows as [ips_row_id, ips_item_id, ips_site_id, ips_site_page].
    """
    s = values_str
    n = len(s)
    i = 0

    while i < n:
        while i < n and s[i] != "(":
            i += 1
        if i >= n:
            break
        i += 1  # '('

        row = []
        while True:
            while i < n and s[i] == " ":
                i += 1

            if i < n and s[i] == "'":  # string
                i += 1
                buf = []
                while i < n:
                    c = s[i]
                    if c == "\\":  # escape
                        if i + 1 < n:
                            buf.append(s[i + 1])
                            i += 2
                        else:
                            i += 1
                        continue
                    if c == "'":
                        i += 1
                        break
                    buf.append(c)
                    i += 1
                val = "".join(buf)
            else:  # number / NULL
                j = i
                while j < n and s[j] not in ",)":
                    j += 1
                token = s[i:j].strip()
                val = None if token == "NULL" else int(token)
                i = j

            row.append(val)

            if i < n and s[i] == ",":
                i += 1
                continue
            elif i < n and s[i] == ")":
                i += 1
                break
            else:
                while i < n and s[i] not in ",)":
                    i += 1
                if i < n and s[i] == ",":
                    i += 1
                    continue
                if i < n and s[i] == ")":
                    i += 1
                    break

        yield row

        while i < n and s[i] in ", \n\r\t":
            i += 1


def site_id_to_language(site_id: str) -> str:
    return site_id[:-4] if site_id.endswith("wiki") else site_id


def extract_to_df(sql_gz_path: str, keep_sites=None, limit=None, normalize_title=True) -> pd.DataFrame:
    keep_sites = set(keep_sites) if keep_sites else None
    rows = []
    count = 0

    with gzip.open(sql_gz_path, "rt", encoding="utf-8", errors="replace") as f:
        pbar = tqdm(f, desc="Reading .sql.gz", unit="lines", mininterval=0.5)

        for line in pbar:
            if not line.startswith(INSERT_PREFIX):
                continue

            values_part = line[len(INSERT_PREFIX):].rstrip(";\n")
            for ips_row_id, ips_item_id, ips_site_id, ips_site_page in parse_mysql_tuples(values_part):
                if keep_sites and ips_site_id not in keep_sites:
                    continue

                qid = f"Q{ips_item_id}"
                lang = site_id_to_language(ips_site_id)
                title = ips_site_page.replace("_", " ") if normalize_title else ips_site_page

                rows.append((qid, lang, title))
                count += 1

                # update tqdm postfix occasionally 
                if count % 100_000 == 0:
                    pbar.set_postfix(rows=count)

                if limit is not None and count >= limit:
                    pbar.set_postfix(rows=count)
                    return pd.DataFrame(rows, columns=["QID", "Language", "Title"])

        pbar.set_postfix(rows=count)

    return pd.DataFrame(rows, columns=["QID", "Language", "Title"])

if __name__ == "__main__":
    INSERT_PREFIX = "INSERT INTO `wb_items_per_site` VALUES "

    start_time = time.perf_counter()

    df = extract_to_df(
        sql_gz_path=os.path.join(DATA_DIR, "wikidata/raw", "wikidatawiki-20251201-wb_items_per_site.sql.gz"),
        keep_sites=None, 
        limit=None,                     
        normalize_title=True
    )

    extract_time = time.perf_counter() - start_time

    print(df.head())
    print(len(df))
    print(f"Extraction time: {extract_time:.2f} seconds")

    output_path = os.path.join(DATA_DIR, "wikidata/processed", "wb_items_per_site.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)

    df_cui = pd.read_csv(os.path.join(DATA_DIR, "wikidata/", "qid_cui.csv"))
    df_cui["QID"] = df_cui["qid"].str.extract(r"(Q\d+)", expand=False)

    qid_list = df_cui["QID"].dropna().unique().tolist()
    qid_set = set(qid_list)
    df_filtered = df[df["QID"].isin(qid_set)].copy()

    qid_to_cui = df_cui[["QID", "cui"]].dropna().drop_duplicates()
    df_filtered = df_filtered.merge(qid_to_cui, on="QID", how="left")
    df_filtered = df_filtered.rename(columns={"cui": "CUI"})

    output_path = os.path.join(DATA_DIR, "wikidata/processed", "wb_items_per_site_filtered.csv")
    df_filtered.to_csv(output_path, index=False)

    total_time = time.perf_counter() - start_time
    print(f"Total runtime: {total_time:.2f} seconds")

