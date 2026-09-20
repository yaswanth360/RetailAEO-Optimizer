# Contributing

Thanks for helping sellers show up in AI answers. Small, focused pull requests are easiest to review.

## Set up

```bash
git clone https://github.com/YOUR-USERNAME/surfaced.git && cd surfaced
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
```

## Good first contributions

- A new engine adapter (Microsoft Copilot, Google AI Mode, Meta AI, You.com). See `docs/EXTENDING.md`.
- Better answer parsing in `surfaced/extract.py` (structured product cards, tables, non-English answers).
- New content channels (Pinterest, LinkedIn, Shopify blog) in `surfaced/agents/content.py`.
- A video renderer that calls an image or video generation API.
- Translations of the dashboard and README.

## Ground rules

1. **No scraping behind logins and no terms-of-service evasion.** Marketplace assistants are handled by importing answers the user captured themselves. PRs that automate logged-in sessions will not be merged.
2. **No fake engagement.** No fake reviews, sockpuppet accounts, or undisclosed promotion. Generated content must keep the disclosure line and the `[VERIFY]` markers.
3. **No invented facts.** Templates and prompts may only use data from the product profile.
4. **Keep demo data fictional.** Never ship simulated scores for real brands.
5. Add or update tests for behavior changes, and run `python scripts/refresh_demo_ui.py` if scoring, recommendations or content templates change.

## Pull request checklist

- [ ] `pytest -q` passes
- [ ] New env vars are documented in `.env.example`
- [ ] User-facing changes are described in the README or docs
