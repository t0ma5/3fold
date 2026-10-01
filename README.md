# TFT ledger overview

Static snapshot of ThreeFold TFT supply, each TFT counted once. The site is [3fold.pages.dev](https://3fold.pages.dev).

Numbers live in `site/snapshot.json`. Names, notes, and the written sections stay as edited. `scripts/refresh_snapshot.py` rewrites balances, shares, and the dates only.

## Weekly refresh

GitHub Actions runs `.github/workflows/refresh.yml` every Monday at 06:00 UTC. The Actions tab can also run **Refresh TFT snapshot** by hand.

The job updates the snapshot, commits it, and deploys the `site` folder to the Cloudflare Pages project `3fold` (production branch `3fold`).

Repository secrets, set in GitHub and never committed:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

## Local check

```bash
pip install -r requirements.txt
python scripts/refresh_snapshot.py
```
