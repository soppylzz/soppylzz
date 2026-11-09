"""Generate a self-contained stats card using public GitHub REST data."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def github(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def main():
    user = github("users/soppylzz")
    repos = []
    page = 1
    while True:
        batch = github(f"users/soppylzz/repos?type=owner&per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    stars = sum(repo["stargazers_count"] for repo in repos if not repo["fork"])
    metrics = [
        ("Public repos", user["public_repos"]),
        ("Followers", user["followers"]),
        ("Stars · owned repos", stars),
    ]
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cells = "\n".join(
        f'<text x="{32 + index * 228}" y="102" class="value">{value:,}</text>'
        f'<text x="{32 + index * 228}" y="130" class="label">{label}</text>'
        for index, (label, value) in enumerate(metrics)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="194" viewBox="0 0 720 194" role="img" aria-labelledby="title desc">
  <title id="title">soppylzz · GitHub stats</title>
  <desc id="desc">{user['public_repos']} public repositories, {user['followers']} followers, {stars} stars on owned non-fork repositories. Updated {updated} UTC.</desc>
  <style>
    .bg {{ fill: #fff; stroke: #d0d7de; }}
    text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .heading {{ fill: #82506b; font-size: 17px; font-weight: 600; }}
    .value {{ fill: #1f2328; font-size: 30px; font-weight: 600; }}
    .label, .footer {{ fill: #59636e; font-size: 13px; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #0d1117; stroke: #3d444d; }}
      .heading {{ fill: #e5a6ba; }}
      .value {{ fill: #f0f6fc; }}
      .label, .footer {{ fill: #b1bac4; }}
    }}
  </style>
  <rect x="0.5" y="0.5" width="719" height="193" rx="12" class="bg"/>
  <text x="32" y="38" class="heading">GitHub / soppylzz</text>
  {cells}
  <text x="32" y="172" class="footer">Public data · excludes stars on forks · updated {updated} UTC</text>
</svg>
'''
    # Fetch and render everything before replacing the last good snapshot.
    target = Path(__file__).resolve().parents[1] / "assets/stats.svg"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(svg, encoding="utf-8")
    temporary.replace(target)


if __name__ == "__main__":
    main()
