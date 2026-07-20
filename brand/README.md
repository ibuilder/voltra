# Voltra — brand assets

Concept: a lightning bolt (volt) whose descent-and-rebound reads as a price move
breaking up through a resistance level — a nod to the TrendBreak strategy.

Palette:  Ink #0B1220 · Cyan #2DE2E6 · Indigo #4F46E5 · Violet #7C3AED
Wordmark: Space Grotesk Bold (tagline: Space Grotesk Medium)

## logo/
- voltra-logo.svg          Primary lockup, transparent (system-font fallback for wordmark)
- voltra-logo-render.svg   Same, referencing the exact "Space Grotesk Bold" family
- voltra-icon.svg          App-icon tile (dark rounded square + gradient bolt)
- voltra-logo.png / @3x    Raster lockup (960 / 1440 px wide, transparent)
- voltra-logo-inverted.png Light wordmark for dark backgrounds (transparent)
- voltra-logo-tagline.png  Lockup with "CRYPTO TRADING ENGINE"
- voltra-icon-1024.png     Master icon tile

## favicon/  (web + dashboard)
favicon.ico (16/32/48) · favicon-16/32/48.png · apple-touch-icon-180.png
icon-192.png · icon-512.png · maskable-512.png (Android safe-zone)

Suggested <head>:
  <link rel="icon" href="/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" href="/icon-512.png" sizes="512x512">
  <link rel="apple-touch-icon" href="/apple-touch-icon-180.png">

## tauri/  (desktop controller)
Drop into desktop/src-tauri/icons/. Includes 32x32, 128x128, 128x128@2x,
icon.png (512), Windows Square*Logo set, and StoreLogo.
Generate platform icon.ico/icon.icns with:  cargo tauri icon logo/voltra-icon-1024.png
