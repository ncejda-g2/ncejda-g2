## 1. Trending collection and state
- [x] 1.1 Add typed models and a parser for GitHub daily, weekly, and monthly Trending pages.
- [x] 1.2 Fetch the three Trending windows with bounded timeouts, descriptive user-agent headers, deduplication, and graceful failure behavior.
- [x] 1.3 Add dated snapshot persistence and a stable-ID feature ledger with seven-day cooldown calculations.
- [x] 1.4 Derive daily observed streaks, current rank, and period-star metadata from saved snapshots.

## 2. Classification and enrichment
- [x] 2.1 Fetch repository metadata and bounded README excerpts for uncached candidates.
- [x] 2.2 Add a capability-limited structured classifier implementing broad but material AI relevance.
- [x] 2.3 Cache classification results with enough repository/README identity to permit safe refreshes.
- [x] 2.4 Search HN Algolia for selected repositories and produce a sourced independent-reaction field or an explicit no-discussion result.

## 3. Selection and rendering
- [x] 3.1 Select up to three `Still Trending` repositories by current daily rank.
- [x] 3.2 Select up to three full write-ups using daily, weekly, monthly priority and the seven-day full-feature cooldown.
- [x] 3.3 Extend structured picker/README inputs and render `Trending AI Repositories` beneath `From the AI Labs`, including source-window labels and observed streak wording.
- [x] 3.4 Keep Trending rendering independent of HN/lab no-news mode and update feature history only after a successful README write.
- [x] 3.5 Update the README footer and setup documentation to describe GitHub Trending coverage.

## 4. Verification
- [x] 4.1 Add parser fixtures and tests for GitHub HTML changes, missing fields, and overlapping windows.
- [x] 4.2 Add tests for seven-day eligibility boundaries, streak derivation, stable-ID deduplication, and failed-run bookkeeping.
- [x] 4.3 Add classification cases for AI tools, AI collections, tangential general collections, and prompt-injection-like README text.
- [x] 4.4 Add rendering tests for repeated leaders, fewer than three discoveries, HN reaction presence/absence, and no-news editions.
- [x] 4.5 Run the focused test suite and a non-mutating/dry-run integration check against current source pages.
