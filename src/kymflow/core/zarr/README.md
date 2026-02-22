# kymflow_zarr_tree

This is a small, working code tree implementing:

- **ZarrDataset**: dataset-level API
- **ZarrImageRecord**: per-image object layer
- **Manifest**: dataset-level index (`index/manifest.json.gz`)
- **DatasetSchema**: schema versioning + validation

## Install (typical)
```bash
uv pip install "zarr<3" numcodecs numpy pandas pyarrow
```

## Run the example
From this repo root:
```bash
uv run python examples/ingest_example.py
```

## Layout
- Images stored at: `images/<image_id>/data`
- Analysis blobs stored under: `images/<image_id>/analysis/`
- Manifest stored at: `index/manifest.json.gz`

## Developer Note (Split Repo)
When working against the extracted standalone sibling repo `../acqstore`:

```bash
uv pip install -e ../acqstore
```

Run acqstore tests from the `acqstore/` repo:

```bash
uv run pytest -q
```
