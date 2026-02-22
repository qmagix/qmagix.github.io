# CLAUDE.md

## Project Overview

**8x80 / AIFinds** is a personal homepage and link dashboard hosted on GitHub Pages at `qmagix.github.io`. It provides a curated collection of categorized website links (AI tools, shopping, news, finance, etc.) and a multi-engine search bar that lets users search across Google, Bing, DuckDuckGo, Phind, Reddit, Twitter, and YouTube simultaneously.

## Tech Stack

- **HTML** - Plain static HTML files (no framework, no static site generator, no build step)
- **CSS** - Bootstrap 5.1.0 bundled locally in `css/styles.css` with Start Bootstrap "Simple Sidebar" v6.0.3 template
- **JavaScript** - Vanilla JS, no bundler or transpiler
- **Font Awesome 4.0.0** - Loaded via CDN for icons
- **Bootstrap 5.1.0** - JS loaded via CDN (`cdn.jsdelivr.net`)
- **External API** - Random quotes loaded from `https://www.garage10.com/randquotejs`

## Repository Structure

```
qmagix.github.io/
├── index.html          # Main page - table-based layout with search + categorized links
├── list.html           # Alternative page - list-group layout (older/simpler version)
├── css/
│   └── styles.css      # Bootstrap 5.1.0 + Simple Sidebar CSS (bundled, large file)
├── js/
│   └── scripts.js      # Sidebar toggle logic (DOMContentLoaded handler)
├── assets/
│   └── favicon.ico     # Site favicon
├── README.md           # Minimal project readme
└── CLAUDE.md           # This file
```

## Key Files

### `index.html` (primary page)
- Contains inline `<script>` with search functions: `googlesearch()`, `ducksearch()`, `bingsearch()`, `phindsearch()`, `redditsearch()`, `twittersearch()`, `youtubesearch()`
- All search functions read from input `#q` and open results in a new tab
- Enter key defaults to Google search
- Link categories organized in a `<table>`: HOT1, HOT2, HOT3, BUY, EAT, DEALS, FUN, LEARN, NEWS, TRAVEL, HELP, MONEY, MONEY2, HOUSE, JOBS, OTHERS
- Random quote displayed in a `<blockquote>` at the top, loaded from external script
- Responsive: font-size reduces at `max-width: 1200px`

### `list.html` (secondary page)
- Simpler version using Bootstrap `list-group-horizontal` instead of tables
- Fewer search engines (DuckDuckGo, Google, Bing only)
- Same link categories in a different visual layout
- No random quote feature

### `js/scripts.js`
- Single responsibility: toggles sidebar visibility via `sb-sidenav-toggled` class
- Persists toggle state to `localStorage` under key `sb|sidebar-toggle`

### `css/styles.css`
- Large bundled file containing all of Bootstrap 5.1.0 CSS plus Simple Sidebar custom styles
- Do not manually edit this file - it is a compiled/bundled asset

## Development Workflow

### No Build Step
This is a purely static site. Edit HTML/JS files directly and changes take effect immediately.

### Local Development
Open `index.html` directly in a browser, or use any local server:
```bash
python3 -m http.server 8000
# Then visit http://localhost:8000
```

### Deployment
The site deploys automatically to GitHub Pages from the `main` branch. Push to `main` and changes go live at `https://qmagix.github.io`.

### No Tests / No Linting / No CI
There are no automated tests, linters, or CI pipelines configured.

## Conventions and Patterns

### Link Format
All external links follow this pattern:
```html
<a href="https://example.com" target="_blank" class="text-decoration-none">Label</a>
```
- Always use `target="_blank"` for external links
- Always use `class="text-decoration-none"` to remove underlines

### Adding a New Link Category (index.html)
Add a new `<tr>` inside the `<tbody>` of the main table:
```html
<tr>
    <td><b>CATEGORY</b></td>
    <td><a href="https://site1.com" target="_blank" class="text-decoration-none">Site1</a></td>
    <td><a href="https://site2.com" target="_blank" class="text-decoration-none">Site2</a></td>
    <!-- up to 5 links per row -->
</tr>
```

### Adding a New Search Engine
1. Add a search function in the inline `<script>` block at the top of `index.html`
2. Add a corresponding `<button>` in the input group with an `onclick` handler
3. Follow the existing pattern: read from `document.getElementById("q").value` and `window.open()` to the search URL

### Sidebar
The sidebar uses Bootstrap's offcanvas-style toggle pattern from the Simple Sidebar template. Sidebar items currently link to `#!` (placeholder/non-functional).

## Known Issues
- Some search functions use `q.value` (global element reference) instead of the local `text` variable - inconsistent but functional in most browsers
- The `list.html` AliExpress link has a malformed URL (`whttp://ww.AliExpress.com`)
- The TRAVEL category Booking link incorrectly points to `ebay.com` in both pages
- The OTHERS category HomeDepot link points to `monster.com`
- Sidebar nav items (`Dashboard`, `Suggestion`, `Donate`, `Contact`, `About`) are non-functional placeholders (`#!`)

## Branch Strategy
- `main` - Production branch, auto-deploys to GitHub Pages
- Feature branches for development work
