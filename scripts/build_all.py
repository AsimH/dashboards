"""Build every dashboard. Single entry point GitHub Actions calls.

Each dashboard's main() writes an HTML file into output/, which the
workflow then deploys to GitHub Pages. We also emit a minimal
output/index.html so the Pages root links to the built dashboards.
"""

import os
import sys
import traceback
from datetime import datetime, timezone

from dashboards import markets_tracker
from dashboards import commodities
from dashboards import stock_alert_tracker

OUTPUT_DIR = "output"


DASHBOARDS = [
    ("markets_tracker", "Markets tracker",
     lambda: markets_tracker.main(out_path=os.path.join(OUTPUT_DIR, "markets_tracker.html"))),
    ("commodities", "Commodities",
     lambda: commodities.main(out_path=os.path.join(OUTPUT_DIR, "commodities.html"))),
    ("stock_alert_tracker", "Stock Alert Tracker",
     lambda: stock_alert_tracker.main(out_path=os.path.join(OUTPUT_DIR, "stock_alert_tracker.html"))),
]


def _write_index(built: list[tuple[str, str]]) -> None:
    """Minimal landing page linking each built dashboard. Placeholder — restyle freely."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    links = "\n".join(
        f'    <li><a href="{slug}.html">{label}</a></li>' for slug, label in built
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dashboards</title>
<style>
  body {{ background:#faf8f3; color:#2b2b2b; font-family:Inter,system-ui,sans-serif;
         max-width:40rem; margin:4rem auto; padding:0 1.5rem; }}
  h1 {{ font-family:"Cormorant Garamond",Georgia,serif; font-weight:600; }}
  ul {{ list-style:none; padding:0; }}
  li {{ margin:.6rem 0; }}
  a {{ color:#9a3b1b; text-decoration:none; font-size:1.15rem; }}
  a:hover {{ text-decoration:underline; }}
  .stamp {{ color:#7a766e; font-family:"JetBrains Mono",monospace; font-size:.8rem; margin-top:2rem; }}
</style></head><body>
  <h1>Dashboards</h1>
  <ul>
{links}
  </ul>
  <div class="stamp">built {stamp}</div>
</body></html>
"""
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    failed, built = [], []
    for slug, label, build in DASHBOARDS:
        print(f"\n=== Building {slug} ===")
        try:
            build()
            built.append((slug, label))
        except Exception:
            print(f"!! {slug} failed:")
            traceback.print_exc()
            failed.append(slug)

    _write_index(built)

    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"All {len(DASHBOARDS)} dashboards built successfully -> {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
