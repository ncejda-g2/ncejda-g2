# Change: Add trending AI repository coverage

## Why
The daily newspaper currently covers Hacker News and official AI lab posts but does not represent projects gaining unusual attention on GitHub. Simply suppressing recently featured repositories would hide sustained popularity, while repeatedly publishing the same full write-up would crowd out discovery.

## What Changes
- Scrape GitHub's daily, weekly, and monthly Trending repository pages during each newspaper run.
- Broadly classify repositories for material AI relevance by inspecting repository metadata and a bounded README excerpt; collections and resource lists remain eligible when AI is their organizing subject.
- Add a `Trending AI Repositories` section beneath `From the AI Labs` with two lanes:
  - a compact `Still Trending` list for recently featured AI repositories that continue to appear on Daily Trending;
  - up to three `New and Noteworthy` full write-ups selected from daily, then weekly, then monthly Trending.
- Allow a repository to receive another full write-up seven calendar days after its prior full feature.
- Save daily Trending snapshots so the newspaper can report observed streaks and ranks without claiming historical data GitHub does not provide.
- Search Hacker News for each full-write-up repository and summarize a substantive third-party reaction when one exists; explicitly report when none is found and never manufacture criticism.
- Treat repository README text as untrusted input and classify it without shell or file-writing capabilities.

## Impact
- Affected specs: `daily-ai-trending` (new capability)
- Affected code: `daily_agent/agent.py`, README rendering prompts, new Trending state under `daily_agent/data/`, dependency declarations if required
- External sources: GitHub Trending HTML, GitHub repository metadata/README endpoints, Hacker News Algolia API
