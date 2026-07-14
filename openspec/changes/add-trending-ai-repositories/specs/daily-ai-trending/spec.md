## ADDED Requirements

### Requirement: Multi-window Trending collection
The system SHALL collect GitHub repository rankings from the daily, weekly, and monthly Trending views for each newspaper edition and SHALL retain each repository's source window and displayed rank.

#### Scenario: All Trending windows are available
- **WHEN** GitHub returns valid daily, weekly, and monthly Trending pages
- **THEN** the system records the ordered repositories from all three windows
- **AND** deduplicates the selection pool by stable repository identity

#### Scenario: A Trending source is unavailable
- **WHEN** one or more Trending pages cannot be fetched or parsed
- **THEN** the system logs the failure and continues with the available windows
- **AND** does not fail unrelated Hacker News, lab, or comic generation solely because Trending is unavailable

### Requirement: Broad material AI classification
The system SHALL treat a repository as eligible when AI is plausibly material to its primary purpose, product, content, or organizing subject and SHALL default toward inclusion for borderline AI relevance.

#### Scenario: AI collection qualifies
- **WHEN** a Trending repository is a curated collection whose organizing subject is AI projects, prompts, models, or resources
- **THEN** the system classifies it as AI-related even if it is not executable software

#### Scenario: AI is merely incidental
- **WHEN** a general-purpose repository contains some AI entries but its organizing subject is not materially AI-related
- **THEN** the system does not classify it as AI-related solely because those entries exist

#### Scenario: Repository content is untrusted
- **WHEN** repository README text is supplied for classification
- **THEN** the system bounds and identifies the text as untrusted input
- **AND** the classifier has no shell or filesystem-write capability

### Requirement: Sustained-trend representation
The system SHALL render up to three recently featured AI repositories that remain on the current Daily Trending view in a compact `Still Trending` list ordered by current daily rank.

#### Scenario: Previously featured repository remains daily trending
- **WHEN** an AI repository was fully featured fewer than seven calendar days ago
- **AND** it appears on the current Daily Trending view
- **THEN** the system may display it in `Still Trending`
- **AND** includes its current rank and observed consecutive-edition streak

#### Scenario: Streak label is rendered
- **WHEN** consecutive daily snapshots contain the same repository
- **THEN** the displayed streak is derived from those snapshots
- **AND** is labeled as observed rather than as complete GitHub history

### Requirement: Fresh repository write-ups
The system SHALL render up to three full `New and Noteworthy` write-ups, considering eligible AI repositories in rank order from daily, then weekly, then monthly Trending.

#### Scenario: Daily candidates fill the section
- **WHEN** at least three eligible daily AI repositories are available
- **THEN** the system selects the first three in Daily Trending order
- **AND** does not use weekly or monthly candidates

#### Scenario: Weekly or monthly fallback is needed
- **WHEN** fewer than three eligible daily AI repositories are available
- **THEN** the system fills remaining slots from Weekly Trending in rank order
- **AND** then from Monthly Trending in rank order if needed
- **AND** labels each write-up with its source window and rank

#### Scenario: Fewer than three candidates exist
- **WHEN** fewer than three eligible candidates exist across all windows
- **THEN** the system publishes the available write-ups without recycling a cooldown-ineligible repository or fabricating an entry

### Requirement: Seven-day full-feature cooldown
The system SHALL make a previously featured repository eligible for another full write-up when at least seven calendar days have elapsed since its last successful full feature.

#### Scenario: Repository is inside cooldown
- **WHEN** fewer than seven calendar days have elapsed since a repository's last successful full feature
- **THEN** the repository is excluded from `New and Noteworthy`

#### Scenario: Repository reaches cutoff
- **WHEN** seven or more calendar days have elapsed since a repository's last successful full feature
- **THEN** the repository is eligible for selection again according to source-window priority and rank

#### Scenario: README generation fails
- **WHEN** a repository is selected but the edition's README write does not complete successfully
- **THEN** the system does not advance that repository's last-full-feature date

### Requirement: Factual full write-ups
Each full write-up SHALL link the repository, state its Trending source and rank, and provide a concise factual explanation based on repository metadata and README content.

#### Scenario: Repository is selected
- **WHEN** a repository is selected for a full write-up
- **THEN** the rendered entry includes its repository link, source window, rank, project type, and concise summary

### Requirement: Sourced independent reactions
The system SHALL search Hacker News for each full-write-up repository and SHALL only publish independent reaction summaries grounded in a linked HN discussion.

#### Scenario: Substantive HN discussion exists
- **WHEN** a relevant HN discussion contains a substantive third-party reaction
- **THEN** the system summarizes the reaction with narrow attribution
- **AND** links the discussion
- **AND** may report positive, mixed, or critical reactions

#### Scenario: No substantive HN discussion exists
- **WHEN** no relevant substantive HN discussion is found
- **THEN** the system states that no substantive independent discussion was found
- **AND** does not invent criticism or an unsourced trade-off

### Requirement: README placement and independence
The system SHALL place `Trending AI Repositories` immediately beneath `From the AI Labs` and SHALL render it independently of whether Hacker News or lab posts were found.

#### Scenario: Other news sources are empty
- **WHEN** no eligible Hacker News stories or AI lab posts exist but Trending data is available
- **THEN** the README still renders the Trending section
