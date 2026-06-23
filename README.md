# dashboards

Daily **markets & commodities** dashboards. Built by GitHub Actions and
published to **GitHub Pages**.

| dashboard | source |
|---|---|
| `markets_tracker` | yfinance panel |
| `commodities` | yfinance panel |

## Layout
```
dashboards/
  dashboards/        # the dashboard modules
  src/dashlib/       # fetch_yfinance_panel, pct_return, momentum_score
  scripts/build_all.py        # also writes output/index.html
  .github/workflows/build.yml # daily cron + Pages deploy
  output/            # built HTML (git-ignored; Actions builds fresh)
```

## Run locally
```bash
uv sync
uv run python scripts/build_all.py      # -> output/markets_tracker.html, commodities.html, index.html
```

## Deploy (GitHub Pages)
1. Create the repo on GitHub and push (see below).
2. Repo **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. The workflow runs on push, daily at **23:11 UTC** (03:11 Abu Dhabi), and on
   manual **Run workflow** from the Actions tab. Adjust the cron in
   `.github/workflows/build.yml` if you want a different time.

## First push to GitHub
```bash
cd dashboards
git init
git add .
git commit -m "Initial dashboards build"
git branch -M main
git remote add origin https://github.com/<your-username>/dashboards.git
git push -u origin main
```
Later updates:
```bash
git add -A
git commit -m "describe the change"
git push
```

## Notes
- `output/index.html` is a minimal placeholder landing page — restyle or
  remove it in `scripts/build_all.py`.
- `dashlib` here is trimmed to what these two dashboards use.
