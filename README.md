# The Ascent

Automatic news site for ambitious women in the corporate world, in English, Spanish and French.

- `ascent_news.py` collects news, has Claude research and write the articles, draws the illustrations and builds the website in `site/`.
- `data/articles.json` is the archive (the site's memory).
- `.github/workflows/update.yml` runs everything three times a day and publishes to GitHub Pages.

Run locally: `python ascent_news.py` (needs `ANTHROPIC_API_KEY` in a `.env` file).
Rebuild the site without new news: `python ascent_news.py --build-only`.
