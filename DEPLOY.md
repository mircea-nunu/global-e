# Deploying this assignment site to GitHub Pages

This repository includes a ready-made static site in `site/` that uses Plotly.js to render interactive charts from the CSV exports in `exports/`.

Steps to publish:

1. Create a new GitHub repository and push this workspace to it.

```powershell
git init
git add .
git commit -m "assignment"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

2. The GitHub Actions workflow in `.github/workflows/deploy.yml` runs on pushes to `main`. It copies `exports/*.csv` into `site/exports/` and publishes `site/` to the `gh-pages` branch.

3. After the workflow finishes, open `https://<your-user>.github.io/<your-repo>/` to view the site.

Notes:
- If you fork this repository, update the `remoteBase` URL in `site/index.html` so the dashboard loads CSVs from your repository.
- If you prefer a different publish path, edit `publish_dir` in the workflow.
- The site reads CSV files client-side, so the exports must remain available in the published site or the remote fallback URL must be correct.
