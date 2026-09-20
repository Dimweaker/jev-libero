# Decision Lab

The project's GitHub Pages showcase: recorded video, Jev's three decision layers, choice probabilities, physical progress, and gripper trajectories on one playback clock.

## Preview locally

From the repository root:

```bash
pip install -e .
python tools/build_site.py --out _site
python -m http.server 8080 --directory _site
```

Open `http://localhost:8080`. The page is static HTML/CSS/JavaScript; visitors do not need an API key or simulator.

## Data and timing

`tools/build_site.py` exports the two featured seed-1 recordings from `examples/records/` and copies their MP4s. The generated `_site/` folder contains the deployable website.

- Each primitive's recorded step count defines its video interval, including the shorter final actions.
- The 20 Hz progress curve comes from saved simulator states. Render frame zero follows the first control step, so video frame `i` corresponds to measured state `i + 1`.
- Solid spatial paths connect measured end-effector positions at decision boundaries. Dashed branches show candidate forecast endpoints. The XZ/XY/YZ selector preserves spatial proportions.
- Choice probabilities, confidence, prompts, and responses come directly from API logs. A retained intent/strategy points back to its original call, with the originating decision displayed.
- The video clock drives all views. Default playback is ¼ speed; reduced-motion preferences start the player paused and disable decorative animation.

## Development

```bash
cd site
npm ci
npm test
npx playwright install chromium
npm run test:browser
npm run format
```

Build `_site/` before testing. Browser checks serve the site under `/jev-libero/`, exercise all 34 decisions, validate both video durations and final states, and capture desktop/mobile screenshots in `site/test-results/`.

The page's visual direction draws on the oversized typography and color treatments of [TypeSafe](https://typesafe.ai), the simulation-first presentation of [JevPilot](https://github.com/standardagents/jevpilot), and the probability dashboard of [TypeSafe Mario](https://github.com/fhshaik/typesafe-mario). The website implementation and graphics are original; no third-party site assets are bundled.

## Publishing

Set the repository's **Settings → Pages → Source** to **GitHub Actions**. `.github/workflows/pages.yml` builds, checks, and deploys changes to the site, source records, or videos on `main`.

Public address: https://dimweaker.github.io/jev-libero/
