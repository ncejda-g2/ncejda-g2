## Context
GitHub Trending exposes separate daily, weekly, and monthly views but no documented API. Daily rankings can be dominated by the same repositories for several editions. The newspaper needs to preserve that signal while still offering fresh discoveries and avoiding unsupported editorial claims.

The current pipeline fetches source material in Python, delegates editorial decisions to Claude, and passes structured data into a separate README-writing call. Trending coverage should follow the same pattern while keeping selection and history deterministic.

## Goals / Non-Goals

### Goals
- Represent sustained dominance on Daily Trending without repeating full prose every day.
- Produce up to three fresh or cooldown-eligible AI repository write-ups per edition.
- Prefer inclusion for repositories whose primary purpose or organizing subject is materially AI-related.
- Make the origin and rank of every selected repository transparent.
- Add sourced, non-promotional community context when Hacker News coverage exists.
- Preserve enough daily history to calculate observed streaks and diagnose selections.

### Non-Goals
- Reconstruct GitHub's private Trending algorithm.
- Calculate global star velocity independently of GitHub Trending.
- Guarantee exactly three full write-ups when insufficient eligible repositories exist.
- Perform general web reputation research in V1.
- Treat stars or Trending placement as a security review.

## Decisions

### Decision: Use two editorial lanes
`Still Trending` contains up to three recently featured repositories that remain on the current Daily Trending page, ordered by current daily rank. These compact entries show rank, stars gained for the displayed period when available, and a streak derived from consecutive newspaper snapshots.

`New and Noteworthy` contains up to three full write-ups. Candidates are considered in GitHub order from Daily Trending first, then Weekly Trending, then Monthly Trending. The entry identifies its source window and rank. A repository becomes eligible for another full write-up when `edition_date - last_full_featured_date >= 7` calendar days.

Alternatives considered:
- Suppress all recent repeats: rejected because it hides sustained dominance and can make the section misleadingly empty.
- Repeat the exact top three every day: rejected because it offers little discovery value.
- Merge all windows into one score: rejected because GitHub's windows are not directly comparable and a custom score would obscure provenance.

### Decision: Persist source snapshots and feature history separately
Each successful fetch produces a dated snapshot containing repository identity, rank, window, GitHub-provided period stars when available, and cached classification metadata. A separate feature ledger records the last successful full-feature date by stable GitHub repository ID, with `owner/name` retained for readability.

Observed streaks are derived from consecutive daily snapshots. The rendered label uses `observed streak` so it does not imply continuous monitoring between editions.

Feature history is updated only after the README write succeeds. This prevents a failed edition from consuming a repository's cooldown.

### Decision: Use broad but material AI relevance
Classification defaults toward inclusion when AI is plausibly central to the repository's product, content, or organizing subject. Applications, libraries, models, research repositories, prompt/skill collections, and curated AI resource lists can qualify.

A general-purpose collection is not AI-related merely because some entries mention AI. Classification uses repository description, topics, and the beginning of the README rather than the newest entries alone.

### Decision: Keep untrusted README classification capability-limited
Python fetches and size-limits repository text. The classifier receives the text as explicitly untrusted content and has no shell, filesystem-write, or repository mutation tools. It returns structured fields including eligibility, project type, summary, and rationale.

This is lightweight privilege separation rather than VM-level sandboxing.

### Decision: Hacker News is the only independent-reaction source in V1
For full write-ups, the pipeline searches HN Algolia using the canonical GitHub URL, `owner/name`, and repository name. When a relevant discussion exists, the agent summarizes one or two substantive comments and links the discussion. The summary must use narrow attribution and must not turn isolated comments into community consensus.

If no substantive discussion is found, the entry says so. Positive, mixed, and critical reactions are all valid. GitHub issues and general web search are deferred because they require more source-quality and representativeness judgment.

## Risks / Trade-offs
- GitHub can change Trending HTML. Mitigation: isolate parsing, retain fixtures, and fail gracefully without breaking the rest of the newspaper.
- Daily snapshots observe only the scheduled fetch time. Mitigation: label streaks as observed.
- HN coverage will be sparse. Mitigation: make reactions optional and explicitly report absence.
- Broad AI inclusion can create borderline classifications. Mitigation: store classification rationale and cover representative tests, including general collections with incidental AI entries.
- Repository text can attempt prompt injection. Mitigation: bound, delimit, and capability-limit classification input.
- Weekly and monthly results can overlap daily results. Mitigation: deduplicate by stable repository ID before selection while retaining the highest-priority source window.

## Migration Plan
1. Add parser, state models, and tests without changing existing news behavior.
2. Add classification and HN-reaction enrichment.
3. Pass structured Trending data into the README writer and render the new section.
4. Start history from the first successful run; no historical backfill is required.

Rollback consists of disabling the Trending phase and omitting its README block; existing HN, lab, and comic behavior remains independent.

## Open Questions
- None blocking V1. The seven-day cutoff, three-entry lane limits, source order, and HN-only reaction policy are treated as agreed defaults.
