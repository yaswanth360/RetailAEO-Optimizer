# Publishing this repo to GitHub (for the maintainer)

With the GitHub CLI:

```bash
cd surfaced
git init -b main
git add .
git commit -m "Initial release"
gh auth login                                   # once
gh repo create surfaced --public --source=. --push \
  --description "Open-source answer engine optimization agents for retail sellers"
gh repo edit --add-topic aeo --add-topic geo --add-topic ecommerce --add-topic ai-search
```

Without the CLI: create an empty public repo named `surfaced` on github.com (no README, no license), then:

```bash
git init -b main && git add . && git commit -m "Initial release"
git remote add origin https://github.com/YOUR-USERNAME/surfaced.git
git push -u origin main
```

After the first push:

1. Search the repo for `YOUR-USERNAME` and `OWNER` and replace them with your GitHub username (README, CONTRIBUTING).
2. Settings > Pages > Source: GitHub Actions, to host the demo dashboard.
3. Settings > General > enable Issues, and mark the repo as a template if you want a one-click "Use this template" button in addition to forks.
4. Check that `.env` is not in the commit: `git ls-files | grep -x .env` should print nothing.
