# OpenTrading docs site

The public documentation site, built with [Docusaurus](https://docusaurus.io/).
It's a **static** site — no backend, no API keys, and free to host.

## Local development

```bash
cd docs-site
npm install          # first time only
npm start            # dev server with live reload → http://localhost:3000
```

## Build

```bash
npm run build        # static output in ./build
npm run serve        # preview the production build locally
```

## Deploy (pick one — all free)

The build output in `build/` is plain static files. With `baseUrl: '/'` (the
default in `docusaurus.config.js`), any of these work:

### Vercel or Cloudflare Pages (recommended — same as most Docusaurus sites)

1. Push this repo to GitHub.
2. In Vercel / Cloudflare Pages, "Add project" → import the repo.
3. Set **Root directory** = `docs-site`, **Build command** = `npm run build`,
   **Output directory** = `build`.
4. Deploy. You get a `*.vercel.app` / `*.pages.dev` URL; add a custom domain if
   you like.

### GitHub Pages

- **User/org site** (`orangejustin.github.io`): keep `baseUrl: '/'`.
- **Project site** (`orangejustin.github.io/OpenTrading/`): set
  `baseUrl: '/OpenTrading/'` in `docusaurus.config.js`, then:

```bash
GIT_USER=orangejustin npm run deploy
```

That builds and pushes to the `gh-pages` branch.

## Editing content

- Docs live in `docs/*.md` — order and grouping are set in `sidebars.js`.
- The landing page is `src/pages/index.js`; feature cards are in
  `src/components/HomepageFeatures/`.
- Theme colors are in `src/css/custom.css`; site config in
  `docusaurus.config.js`.
- Images go in `static/img/` and are referenced as `/img/<name>`.

`node_modules/`, `build/`, and `.docusaurus/` are git-ignored.
