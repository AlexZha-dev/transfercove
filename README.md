# TransferCove · showcase site

The standalone product website for **TransferCove 0.2.3**. This branch contains the static site, not the desktop application.

> [!WARNING]
> TransferCove has **no encryption or authentication**. Files are sent over plain HTTP. Use only a trusted, verified local network. Do not expose the receiver to the public internet or untrusted Wi-Fi.

[Website](https://alexzha-dev.github.io/transfercove/) · [Application repository](https://github.com/AlexZha-dev/transfercove) · [Releases](https://github.com/AlexZha-dev/transfercove/releases)

## Publish from this branch

The site uses plain HTML, CSS, and JavaScript. No packages, build command, secrets, or custom Actions workflow are required.

1. Push the site changes: `git push origin showcase-site`.
2. In the repository, open **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
4. Select **showcase-site** and **/(root)**, then click **Save**.
5. Check the Pages deployment under **Actions**. Once it finishes, open <https://alexzha-dev.github.io/transfercove/>.

Subsequent pushes to `showcase-site` publish the updated website automatically. Do not select `/docs`: that directory only contains screenshots. There is no need to merge the site branch into the application’s `main` branch.

The root `.nojekyll` file disables Jekyll processing. Local resource links are relative to `index.html`, so the site works under the GitHub project path `/transfercove/` as well as at a domain root. If the repository is renamed or a custom domain is added, update the canonical and Open Graph URLs in `index.html` and the website links in this README.

See GitHub’s [publishing source documentation](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site) for the repository settings.

## Local preview

Open `index.html` directly in a browser, or run this command from the branch root:

```sh
python -m http.server 8000 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8000/>. Stop the preview with `Ctrl+C`.

## Files and maintenance

| File | Purpose |
| --- | --- |
| `index.html` | Product copy, release links, security notice, screenshots, and page metadata |
| `styles.css` | Responsive layout, visual design, keyboard focus, and reduced-motion support |
| `script.js` | Optional screenshot viewer with keyboard navigation and focus restoration |
| `assets/` | Existing application icon and favicon |
| `docs/images/` | Original, uncropped application screenshots |
| `.nojekyll` | Direct static-file publishing with GitHub Pages |

The site has no remote fonts, analytics, CDN dependencies, upload endpoint, or runtime API calls. Navigation, FAQs, release links, and full-size screenshot links work without JavaScript. With JavaScript enabled, screenshots also open in a dialog: use the arrow buttons or arrow keys to navigate and Escape to close it.

For a new release, update the displayed version in `index.html` and this README. Keep release buttons pointed at the repository’s `/releases` page; do not guess build asset names. Keep security wording consistent with the application README and preserve the warning at the top of the page.

Before publishing, check a narrow mobile viewport and a desktop viewport, open all screenshots, and confirm that relative assets load under `/transfercove/`. Commit only site files; local application data and build artifacts are not part of this branch.
