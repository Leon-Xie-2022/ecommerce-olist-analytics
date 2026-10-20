# E-commerce Orders, Delivery & Customer Analytics (Olist)

> Work in progress. Sections marked *TBD* are filled in as each stage is completed.

Python data-quality pipeline → SQL data model and analysis → Power BI dashboard, built on the public
Olist Brazilian E-Commerce dataset. This is an independent practice project on historical Brazilian data;
it is not client work and makes no claims about business impact.

## Data

- Source: [Olist Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) (Kaggle, published by Olist).
- Licence: **CC BY-NC-SA 4.0**. Data © Olist; used here for non-commercial learning. Details and file checksums: [`docs/data_source.md`](docs/data_source.md).
- Raw files are **not** redistributed in this repository. To reproduce, either:
  - **Kaggle CLI** (needs a Kaggle API token in `%USERPROFILE%\.kaggle\kaggle.json`):
    `kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip`
  - **Browser:** sign in to Kaggle, download the ZIP from the link above and extract all CSVs into `data/raw/`.
- Then run `python src/check_raw.py` to confirm all files are present and to print their SHA-256 checksums.

## Project structure

```
ecommerce-olist-analytics/
├── data/raw/          # original CSVs (not committed)
├── data/processed/    # cleaned outputs (not committed)
├── docs/              # data source, data dictionary, ER diagram, metric definitions
├── sql/               # data model and analysis queries (DuckDB)
├── src/               # Python: config, data checks, cleaning, SQL runner
├── notebooks/         # exploration and walk-throughs
├── powerbi/           # .pbix, screenshots, DAX notes
└── reports/           # figures and the one-page analysis brief
```

## Setup (Windows / PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Methods, results, limitations

*TBD.*
