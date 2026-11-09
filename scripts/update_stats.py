"""Generate profile cards from GitHub data; no live card service is needed."""

import json
import subprocess
import textwrap
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ['soppylzz/soppy-vue', 'soppylzz/soppy-slidev',
            'soppylzz/soppy-react', 'yuzur1ha-org/react']
THEMES = {
    'light': ('#ffffff', '#d0d7de', '#1f6feb', '#57606a', '#1f2328'),
    'dark': ('#0d1117', '#30363d', '#58a6ff', '#c9d1d9', '#f0f6fc'),
}


def github(path, *args):
    for attempt in range(3):
        try:
            return json.loads(subprocess.check_output(['gh', 'api', path, *args], text=True))
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def svg(width, height, title, body, theme):
    bg, border, accent, muted, foreground = THEMES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title, quote=True)}">
<title>{escape(title)}</title>
<style>text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }} .title {{ fill: {accent}; font-size: 18px; font-weight: 600; }} .muted {{ fill: {muted}; font-size: 14px; }} .value {{ fill: {foreground}; font-size: 14px; font-weight: 600; }}</style>
<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="10" fill="{bg}" stroke="{border}"/>
{body}
</svg>
'''


def project_card(repo, theme):
    name = repo['name'] if repo['owner']['login'] == 'soppylzz' else repo['full_name']
    # Avoid emoji/font differences in the repository's decorative description prefix.
    lines = textwrap.wrap((repo['description'] or '').lstrip('😎🏊🤠🐦\u200d🔥 \ufe0f'), width=48)[:2]
    body = '<path d="M25 23h13v16H25z M29 23v16 M25 35h13" fill="none" stroke="' + THEMES[theme][3] + '" stroke-width="1.5"/>\n'
    body += f'<text x="49" y="36" class="title">{escape(name)}</text>\n'
    for index, line in enumerate(lines):
        body += f'<text x="24" y="{69+index*22}" class="muted">{escape(line)}</text>\n'
    language = repo['language'] or ''
    body += f'<text x="24" y="137" class="muted">{escape(language)}</text>\n'
    body += f'<text x="235" y="137" class="muted">Stars {repo["stargazers_count"]} · Forks {repo["forks_count"]}</text>'
    return svg(420, 164, f'{repo["full_name"]}: {repo["description"] or ""}', body, theme)


def main():
    repos = []
    page = 1
    while True:
        batch = github(f'users/soppylzz/repos?type=owner&per_page=100&page={page}')
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    projects = [github(f'repos/{name}') for name in PROJECTS]
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
    body = '<text x="24" y="36" class="title">soppylzz’s GitHub Stats</text>\n'
    for index, (label, value) in enumerate(metrics):
        y = 72 + index*29
        body += f'<text x="24" y="{y}" class="muted">{label}</text><text x="445" y="{y}" text-anchor="end" class="value">{value:,}</text>\n'
    body += f'<text x="24" y="237" class="muted">GitHub snapshot · updated {now:%Y-%m-%d} UTC</text>'
    outputs = {}
    for theme in THEMES:
        suffix = '-dark' if theme == 'dark' else ''
        outputs[f'assets/stats{suffix}.svg'] = svg(490, 260, 'soppylzz GitHub Stats snapshot', body, theme)
        for repo in projects:
            outputs[f'assets/projects/{repo["name"]}{suffix}.svg'] = project_card(repo, theme)
    # Keep the previous cards intact if any GitHub request fails.
    for filename, content in outputs.items():
        target = ROOT / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(target)


if __name__ == '__main__':
    main()
