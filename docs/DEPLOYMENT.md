# Deploying KymFlow Documentation to GitHub Pages

This guide explains how to deploy the MkDocs documentation site to GitHub Pages.

## Prerequisites

- MkDocs and dependencies installed: `pip install -e ".[docs]"`
- Git repository with write access
- GitHub repository configured

## Manual Deployment

### First-Time Setup

1. **Build the documentation site:**
   ```bash
   mkdocs build
   ```
   This creates a `site/` directory with the static HTML files.

2. **Deploy to gh-pages branch:**
   ```bash
   mkdocs gh-deploy
   ```
   This command:
   - Builds the site
   - Creates/updates the `gh-pages` branch
   - Pushes to `origin/gh-pages`
   - GitHub Pages will automatically serve from this branch

3. **Configure GitHub Pages (if not already done):**
   - Go to repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `gh-pages` / `/ (root)`
   - Save

### Updating Documentation

After making changes to documentation:

```bash
mkdocs gh-deploy
```

This will rebuild and redeploy the site.

## Automated Deployment

See `.github/workflows/docs.yml` for the GitHub Actions workflow that automatically builds and deploys documentation when tags are pushed.

## Verification

After deployment, the documentation will be available at:
- `https://mapmanager.github.io/kymflow/`

(Replace `mapmanager` with your GitHub username/organization if different)

## Troubleshooting

- **404 errors**: Ensure GitHub Pages is enabled and pointing to the `gh-pages` branch
- **Build errors**: Run `mkdocs build` locally first to catch errors
- **Missing updates**: Clear browser cache or wait a few minutes for GitHub to update
