"""Refresh the existing stats snapshot from GitHub data."""

import json
import subprocess
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def github(path, *args):
    for attempt in range(3):
        try:
            return json.loads(subprocess.check_output(['gh', 'api', path, *args], text=True))
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def stats_card(metrics, updated, theme):
    if theme == 'dark':
        bg, border, tile, ink, muted, accent, tint = (
            '#0d1117', '#30363d', '#161b22', '#f0f6fc', '#9da7b3', '#e5a6ba', '#342330')
    else:
        bg, border, tile, ink, muted, accent, tint = (
            '#ffffff', '#e6dce2', '#faf7f9', '#24212b', '#716977', '#b2597e', '#f4e4ec')
    icons = [
        '<path d="m8 1 2.2 4.5 5 .7-3.6 3.5.8 5L8 12.3l-4.4 2.4.8-5L.8 6.2l5-.7Z"/>',
        '<circle cx="8" cy="8" r="3"/><path d="M0 8h5m6 0h5"/>',
        '<circle cx="4" cy="3" r="2"/><circle cx="4" cy="13" r="2"/><circle cx="13" cy="13" r="2"/><path d="M4 5v6m9 0V7a4 4 0 0 0-4-4H8m2-2L8 3l2 2"/>',
        '<circle cx="8" cy="8" r="6.5"/><path d="M8 4v4m0 3v.1"/>',
        '<path d="M1 2h6l1 2h7v10H1Z"/>',
    ]

    def icon(index, x, y):
        return (f'<g transform="translate({x} {y})" fill="none" stroke="{accent}" '
                f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{icons[index]}</g>')

    body = f'''<rect x="0.5" y="0.5" width="719" height="283" rx="16" fill="{bg}" stroke="{border}"/>
<text x="24" y="38" fill="{ink}" font-size="18" font-weight="600">GitHub activity</text>
<text x="696" y="37" text-anchor="end" fill="{muted}" font-size="13">@soppylzz</text>
'''
    for index, (label, value) in enumerate(metrics[:3]):
        x = 24 + index * 228
        body += f'''<rect x="{x}" y="60" width="216" height="124" rx="12" fill="{tile}"/>
<rect x="{x+16}" y="74" width="28" height="28" rx="8" fill="{tint}"/>
{icon(index, x+22, 80)}
<text x="{x+16}" y="142" fill="{ink}" font-size="34" font-weight="650">{value:,}</text>
<text x="{x+16}" y="165" fill="{muted}" font-size="12">{escape(label)}</text>
'''
    for index, (label, value) in enumerate(metrics[3:]):
        x = 24 + index * 342
        body += f'''<rect x="{x}" y="202" width="32" height="32" rx="10" fill="{tint}"/>
{icon(index+3, x+8, 210)}
<text x="{x+45}" y="215" fill="{ink}" font-size="18" font-weight="600">{value:,}</text>
<text x="{x+45}" y="234" fill="{muted}" font-size="12">{escape(label)}</text>
'''
    body += f'''<path d="M24 251H696" stroke="{border}"/>
<circle cx="28" cy="268" r="3" fill="{accent}"/>
<text x="40" y="272" fill="{muted}" font-size="11">GitHub snapshot</text>
<text x="696" y="272" text-anchor="end" fill="{muted}" font-size="11">Updated {updated:%Y-%m-%d} UTC</text>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="720" height="284" viewBox="0 0 720 284" role="img" aria-labelledby="title desc">
<title id="title">soppylzz’s GitHub Stats</title>
<desc id="desc">{escape('; '.join(f'{label}: {value:,}' for label, value in metrics))}</desc>
<style>text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}</style>
{body}
</svg>
'''


def main():
    repos = []
    page = 1
    while True:
        batch = github(f'users/soppylzz/repos?type=owner&per_page=100&page={page}')
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    now = datetime.now(timezone.utc)
    query = '''query { user(login: "soppylzz") {
      createdAt
      pullRequests { totalCount }
      issues { totalCount }
      contributionsCollection { totalCommitContributions }
      repositoriesContributedTo(contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY], includeUserRepositories: true) { totalCount }
    } }'''
    query = query.replace('contributionsCollection {', f'contributionsCollection(from: "{now.year}-01-01T00:00:00Z", to: "{now:%Y-%m-%dT%H:%M:%SZ}") {{')
    result = github('graphql', '-f', f'query={query}')
    if result.get('errors'):
        raise RuntimeError(result['errors'])
    activity = result['data']['user']
    years = []
    for year in range(int(activity['createdAt'][:4]), now.year + 1):
        end = now.strftime('%Y-%m-%dT%H:%M:%SZ') if year == now.year else f'{year}-12-31T23:59:59Z'
        years.append(f'y{year}: contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{end}") {{ totalCommitContributions }}')
    commits_query = 'query { user(login: "soppylzz") { ' + ' '.join(years) + ' } }'
    yearly = github('graphql', '-f', f'query={commits_query}')
    if yearly.get('errors'):
        raise RuntimeError(yearly['errors'])
    commits = sum(year['totalCommitContributions'] for year in yearly['data']['user'].values())
    stars = sum(repo['stargazers_count'] for repo in repos if not repo['fork'])
    metrics = [
        ('Total stars', stars),
        ('Total commits', commits),
        ('Total PRs', activity['pullRequests']['totalCount']),
        ('Total issues', activity['issues']['totalCount']),
        ('Contributed to (past year)', activity['repositoriesContributedTo']['totalCount']),
    ]
    outputs = {}
    for theme in ['light', 'dark']:
        suffix = '-dark' if theme == 'dark' else ''
        outputs[f'assets/stats{suffix}.svg'] = stats_card(metrics, now, theme)
    # Keep the previous cards intact if any GitHub request fails.
    for filename, content in outputs.items():
        target = ROOT / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(target)


if __name__ == '__main__':
    main()
