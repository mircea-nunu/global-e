# Deploying this assignment site to GitHub Pages

This repository includes a ready-made static site in `assignment_submission/site/` that uses Plotly.js to render interactive charts from the CSV exports in `assignment_submission/exports/`.

Steps to publish (no credentials required in this project):

1. Create a new GitHub repository (public or private) and push your workspace to it. Example:

```bash
git init
git add .
git commit -m "assignment"
git branch -M main
git remote add origin https://github.com/<your-user>/<your-repo>.git
git push -u origin main
```

2. The GitHub Actions workflow `.github/workflows/deploy.yml` triggers on pushes to `main`. It will copy the CSVs from `assignment_submission/exports/` into `assignment_submission/site/exports/` and publish `assignment_submission/site/` to GitHub Pages (gh-pages branch).

3. After the workflow finishes, open `https://<your-user>.github.io/<your-repo>/` to view the site. If it does not appear immediately, wait a minute and refresh.

Notes:
- If you prefer a different publish path, edit `publish_dir` in the workflow.
- The site reads CSV files client-side; ensure `assignment_submission/exports/*.csv` are present in the repo (they are copied by the workflow).
