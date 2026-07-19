# Sources

Technical resources worth remembering. Add rows as found; keep the priority/status columns current so this stays a triage tool, not just a link dump.

**Priority** — P0 canonical (official, read first) · P1 high-value (verified numbers or deep technical content) · P2 useful context (anecdotal but plausible) · P3 low-signal (listicle, self-promo, redundant — skim or skip)
**Type** — Official / GitHub / Forum (HN) / Blog / Social (LinkedIn) / Newsletter-Podcast
**Signal** — the concrete evidence backing the claim: stars, HN points, comment count, or "official"/"anecdotal"/"unverified"
**Relevance** — does this map to a technique or competitor LT should track (High/Med/Low)
**Status** — Unreviewed (default) / Reviewed / Actioned / Discard — update as you triage

## Search & retrieval

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P2 | [Keyword vs Vector vs Hybrid Search](https://medium.com/@bhdilanka/keyword-search-vs-vector-search-vs-hybrid-search-understanding-modern-information-retrieval-33b68425b295) | Blog | anecdotal | Med | Unreviewed | Overview of retrieval approaches; background, not Claude-Code-specific |
| P2 | [Hybrid Search](https://spice.ai/learn/hybrid-search) | Blog (vendor) | vendor explainer | Med | Unreviewed | Spice.ai explainer |

## Claude Code / Codex — token efficiency & cost

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P0 | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Official | official | High | Unreviewed | Anthropic: treat context as finite resource, curate tokens per inference step. Duplicate — same link also under Mastery → Official |
| P0 | [Manage costs effectively](https://code.claude.com/docs/en/costs) | Official | official | High | Unreviewed | Official Claude Code cost/token management docs |
| P0 | [Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction) | Official | official | High | Unreviewed | Official platform docs on context compaction mechanics |
| P0 | [Lessons from building Claude Code: Prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) | Official | official | High | Unreviewed | Caching as the core cost/latency lever |
| P1 | [Usage limit best practices](https://support.claude.com/en/articles/9797557-usage-limit-best-practices) | Official | official | Med | Unreviewed | Help Center guidance on avoiding rate limits |
| P1 | [Tips on how to minimize Codex usage?](https://community.openai.com/t/tips-on-how-to-minimize-codex-usage/1384019) | Official (community) | official thread | Med | Unreviewed | Concrete tips from OpenAI's own community forum |
| P1 | [Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k](https://news.ycombinator.com/item?id=48883275) | Forum (HN) | 704 pts | High | Unreviewed | Measured baseline token overhead comparison |
| P1 | [Universal Claude.md – cut Claude output tokens](https://news.ycombinator.com/item?id=47581701) | Forum (HN) | 471 pts | High | Unreviewed | Technique for trimming CLAUDE.md to cut output verbosity |
| P1 | [12 Ways to Cut Token Consumption in Claude Code](https://www.firecrawl.dev/blog/claude-code-token-efficiency) | Blog (vendor) | specific numbers (91.9%, 85.5%) | High | Unreviewed | Firecrawl blog, benchmarked claims |
| P1 | [Why Claude Code Subagents Burn So Many Tokens](https://youcanbuildthings.com/articles/claude-code-subagents-token-usage/) | Blog | technical depth | High | Unreviewed | Subagents as independently-billed isolated context windows; `CLAUDE_CODE_SUBAGENT_MODEL` gotcha |
| P2 | [Show HN: CodeBurn – Analyze Claude Code token usage by task](https://news.ycombinator.com/item?id=47759035) | Forum (HN) | 112 pts | Med | Unreviewed | Tool classifying session transcripts into 13 task categories |
| P2 | [Excessive token usage in Claude Code](https://news.ycombinator.com/item?id=47096937) | Forum (HN) | 62 pts | Med | Unreviewed | Community diagnosis of token-bloat causes |
| P2 | [How I Cut My Claude Code Token Usage by 60% and Got Better Output](https://dev.to/numbpill3d/how-i-cut-my-claude-code-token-usage-by-60-and-got-better-output-48b0) | Blog | anecdotal, before/after numbers | Med | Unreviewed | Practitioner write-up |
| P2 | [Cut Claude Code's token overhead by 44%](https://dev.to/harivenkatakrishnakotha/how-i-cut-claude-codes-token-overhead-by-44-and-stopped-hitting-usage-limits-mid-session-3fkf) | Blog | anecdotal, numbers | Med | Unreviewed | Stopping mid-session usage-limit hits |
| P2 | [7 Practical Ways to Reduce Claude Code Token Usage](https://www.kdnuggets.com/7-practical-ways-to-reduce-claude-code-token-usage) | Blog (established pub) | KDnuggets | Med | Unreviewed | Established data/ML publication |
| P2 | [How I Cut Claude Code Token Usage by 90%+ With 5 Tools, Custom Hooks, and Enforcement](https://medium.com/@abdulgafoorabid/how-i-cut-claude-code-token-usage-by-90-with-4-tools-custom-hooks-and-enforcement-d3f8d2488cd6) | Blog | anecdotal, concrete stack | Med | Unreviewed | Stacks Codebase Memory MCP + context-mode + RTK + Headroom + Caveman |
| P2 | [How to Reduce Codex CLI & OpenAI API Token Costs](https://inventivehq.com/knowledge-base/openai/how-to-reduce-api-token-costs) | Blog | anecdotal | Med | Unreviewed | Session/context/caching/shell-filtering strategies for Codex CLI |
| P2 | [Claude Code Token Optimization: 19 Changes to Cut Costs (2026)](https://buildtolaunch.substack.com/p/claude-code-token-optimization) | Newsletter | reports 40-70% savings | Med | Unreviewed | Substack piece |
| P3 | [Show HN: Rtk – reduce Claude Code token usage](https://news.ycombinator.com/item?id=47189599) | Forum (HN) | 18 pts | Med | Unreviewed | Launch thread for CLI-output-filtering proxy; low engagement |
| P3 | [10 Tips to Stop Burning Your Tokens in Claude Code](https://medium.com/@habib23me/10-tip-to-stop-burning-your-tokens-in-claude-code-4776d4ac8956) | Blog | unverified | Low | Unreviewed | Generic listicle |
| P3 | [7 Ways to Cut Your Claude Code Token Usage](https://dev.to/boucle2026/7-ways-to-cut-your-claude-code-token-usage-elb) | Blog | unverified | Low | Unreviewed | Generic listicle |
| P3 | [Optimise token usage in Claude Code](https://menetray.com/en/blog/how-optimise-token-usage-claude-code-without-burning-through-your-subscription) | Blog | anecdotal | Low | Unreviewed | Subscription-friendly usage habits |

### GitHub (token efficiency)

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [ccusage/ccusage](https://github.com/ccusage/ccusage) | GitHub | 17.3k stars, 739 forks | High | Unreviewed | CLI analyzing Claude Code/Codex usage from local JSONL; direct competitor/prior art |
| P1 | [anthropics/claude-code issue #49048](https://github.com/anthropics/claude-code/issues/49048) | GitHub (official) | official repo issue | High | Unreviewed | Feature request for built-in token optimization — roadmap signal |
| P1 | [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | GitHub | 29.7k stars | High | Unreviewed | CLI + local analytics dashboard breaking down input/output/cache tokens and cost per session |
| P1 | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | GitHub | 71.7k stars (flagged: low subscribers relative to stars) | High | Unreviewed | Rust CLI proxy claiming 60-90% reduction; verify claims before relying on star count alone |
| P1 | [drona23/claude-token-efficient](https://github.com/drona23/claude-token-efficient) | GitHub | 5.8k stars | High | Unreviewed | Single drop-in CLAUDE.md cutting output verbosity, no code changes — directly comparable technique to LT |
| P2 | [openai/codex issue #19001](https://github.com/openai/codex/issues/19001) | GitHub (official) | official repo issue | Med | Unreviewed | Proposal to add RTK-style shell-output filtering to Codex CLI |
| P2 | [openai/codex issue #14879](https://github.com/openai/codex/issues/14879) | GitHub (official) | official repo issue | Med | Unreviewed | Proposal to reduce token usage for verbose `exec_command` outputs |
| P2 | [openai/codex issue #5085](https://github.com/openai/codex/issues/5085) | GitHub (official) | official repo issue | Med | Unreviewed | Cost tracking & usage analytics feature request |
| P2 | [steipete/codexbar](https://github.com/steipete/codexbar) | GitHub | 18.6k stars | Med | Unreviewed | macOS menu bar app showing usage/limits across 63+ providers |
| P2 | [Maciek-roboblog/Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) | GitHub | 8.5k stars | Med | Unreviewed | Real-time terminal monitor with burn-rate predictions |
| P2 | [Kilo-Org/kilocode discussion #5848](https://github.com/Kilo-Org/kilocode/discussions/5848) | GitHub (discussion) | anecdotal, "saved 10M tokens (89%)" | Med | Unreviewed | CLI-proxy write-up |
| P2 | [junhoyeo/tokscale](https://github.com/junhoyeo/tokscale) | GitHub | 4.5k stars | Med | Unreviewed | Rust CLI + dashboard tracking usage/cost across 40+ coding agents |
| P2 | [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | GitHub | 2.3k stars | Med | Unreviewed | Curated toolkit incl. a cost-mode skill claiming 30-70% savings |
| P2 | [alexgreensh/token-optimizer](https://github.com/alexgreensh/token-optimizer) | GitHub | 1.7k stars | Med | Unreviewed | Finds "ghost tokens": bloated configs, stale memory, compaction loss, model misrouting — interesting diagnostic framing |
| P2 | [nadimtuhin/claude-token-optimizer](https://github.com/nadimtuhin/claude-token-optimizer) | GitHub | 526 stars | Med | Unreviewed | Hooks-based optimizer with concrete case (11,000 → 1,300 tokens) |
| P2 | [ooples/token-optimizer-mcp](https://github.com/ooples/token-optimizer-mcp) | GitHub | 442 stars (low relative to scope claimed) | Med | Unreviewed | MCP server, 65 tools + 7-phase hook system, claims 60-90%+ reduction — verify before trusting |
| P3 | [mm7894215/TokenTracker](https://github.com/mm7894215/TokenTracker) | GitHub | 1,038 stars | Low | Unreviewed | Local-first token/cost tracker across 27 coding tools |
| P3 | [edouard-claude/snip](https://github.com/edouard-claude/snip) | GitHub | 373 stars | Low | Unreviewed | Go CLI proxy (RTK alternative), 60-90% claim |
| P3 | [mag123c/toktrack](https://github.com/mag123c/toktrack) | GitHub | 179 stars | Low | Unreviewed | Ultra-fast Rust token/cost tracker |
| P3 | [Dicklesworthstone/coding_agent_usage_tracker](https://github.com/Dicklesworthstone/coding_agent_usage_tracker) | GitHub | 74 stars | Low | Unreviewed | Rust port of CodexBar's core logic |

### LinkedIn

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [We heard you wanted to use Codex rate limit resets on your own time...](https://www.linkedin.com/posts/openai_we-heard-you-wanted-to-use-codex-rate-limit-activity-7470991162825277441-LbqE) | Social | official OpenAI account | Med | Unreviewed | Announcement: bankable rate-limit resets |
| P2 | [Claude has brought compacting into chats. Here's why this is a big deal.](https://www.linkedin.com/posts/darren-coxon_claude-has-brought-compacting-into-chats-activity-7407339411639672832-6gqA) | Social | practitioner explainer | Med | Unreviewed | Auto-compaction mechanics |
| P2 | [Anthropic Subsidies Tighten, WOZCODE Boosts Claude Efficiency](https://www.linkedin.com/posts/bentcollins_last-month-a-single-claude-user-consumed-activity-7444448271575515136-DFlZ) | Social | notable data point | Med | Unreviewed | Ben Collins: user consumed ~$27k API compute on $200/mo plan |
| P2 | [How to Use /compact Command in Claude Code for Task Switching](https://www.linkedin.com/posts/kylemickey_how-to-switch-between-tasks-in-claude-code-activity-7392963357160501248-6Ngk) | Social | practitioner | Med | Unreviewed | Concrete `/compact` workflow |
| P2 | [Clear vs Compact in Claude Code: Best Practices](https://www.linkedin.com/posts/jdfiscus_claudecode-bestpractices-activity-7415388135443865600-rRS5) | Social | practitioner | Med | Unreviewed | Comparing `/clear` vs `/compact` use cases |
| P3 | [I keep hitting the Claude Code usage limit. So I built Claude Spend...](https://www.linkedin.com/posts/writetoaniketparihar_i-keep-hitting-the-claude-code-usage-limit-activity-7431248823735279617-rRZO) | Social | 155 comments, self-promo | Low | Unreviewed | Founder builds token-analytics tool |
| P3 | [TOON Cuts Claude Code Costs by 30-60%](https://www.linkedin.com/posts/agenisea_feature-request-add-toon-token-oriented-activity-7409696865576771585-ykHF) | Social | unverified claim | Low | Unreviewed | Token-Oriented Object Notation for config files |
| P3 | [Manage Claude Code tokens with ccusage: A simple solution](https://www.linkedin.com/posts/groyse_claude-code-is-great-until-you-smack-into-activity-7369119700938596355-Hfsd) | Social | walkthrough | Low | Unreviewed | Redundant with ccusage GitHub entry above |
| P3 | [5 Habits to Cut Your Claude Token Use](https://www.linkedin.com/posts/analytics-vidhya_5-habits-to-cut-your-claude-token-use-by-activity-7444718907883646977-ZgXf) | Social | official account, listicle | Low | Unreviewed | Analytics Vidhya |
| P3 | [Optimize Claude Code with Opus 4.6 Effort Settings](https://www.linkedin.com/posts/akashm_claude-code-tip-for-all-those-who-are-loving-activity-7427307856330366976-T_96) | Social | anecdotal | Low | Unreviewed | Adjusting model "effort" levels |
| P3 | [How I optimized Claude Code's token usage with a custom...](https://www.linkedin.com/posts/jamiejferguson_when-i-first-started-using-claude-code-he-activity-7392297798127243264-eJVS) | Social | anecdotal | Low | Unreviewed | Custom-workflow optimization story |
| P3 | [7 Ways to Reduce Claude Code Token Consumption](https://www.linkedin.com/posts/wtsorg_claude-code-bill-is-probably-high-for-the-activity-7459857488188747776-Q9wB) | Social | listicle | Low | Unreviewed | Practitioner list post |
| P3 | [5 Claude Quick Tips to Avoid Chat Token Limit](https://www.linkedin.com/posts/derekaweber_5-claude-quick-tips-for-if-you-are-running-activity-7376340791394410496-xKaa) | Social | listicle | Low | Unreviewed | Quick-tip format |
| P3 | [How to avoid token limits with Claude Code and Subagents](https://www.linkedin.com/posts/andrew-ansley-marketing_do-you-run-out-of-tokens-in-your-context-activity-7361978039875899393-j--J) | Social | anecdotal | Low | Unreviewed | Subagent-based context-limit avoidance |
| P3 | [Free Claude Code Dashboard for Token Visibility](https://www.linkedin.com/posts/nateherkelman_most-people-hit-claude-code-session-limits-activity-7452096646407962624-ImDt) | Social | promo | Low | Unreviewed | Free dashboard tool for session limits |
| P3 | [Claude Setup Token for Long-Lived Auth](https://www.linkedin.com/posts/robert-claus-46491364_i-just-learned-about-claude-setup-token-activity-7446940848937865216-jeg-) | Social | tangential | Low | Unreviewed | `claude setup-token` for CI/CD — auth, not cost |
| P3 | [How to find daily/monthly token usage with Claude Code Tips](https://www.linkedin.com/posts/shajeelafzal_claudecode-vibecoding-activity-7360934444255318017-lgK0) | Social | anecdotal | Low | Unreviewed | Practitioner tips post |
| P3 | [Optimize Claude Usage to Avoid Token Limit](https://www.linkedin.com/posts/michaelzick_ive-been-burning-through-my-claude-limit-activity-7446364814270013441-E49h) | Social | anecdotal | Low | Unreviewed | Personal war story |
| P3 | [How to use Claude Code effectively: Providing context for...](https://www.linkedin.com/posts/markshust_one-of-the-biggest-mistakes-i-see-with-claude-activity-7392184912155435009-mixa) | Social | anecdotal | Low | Unreviewed | The biggest context-provision mistake developers make |
| P3 | [RTK Rust Token Killer: 85% menos tokens no Claude Code](https://pt.linkedin.com/pulse/rtk-como-cortei-85-do-consumo-de-tokens-claude-code-witalo-rebou%C3%A7as-utckf) | Social | unverified, non-English | Low | Unreviewed | Redundant with rtk-ai/rtk GitHub entry above |

## Claude Code / Codex — mastery & advanced workflows

### Official / vendor

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P0 | [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) | Official | official | High | Unreviewed | Anthropic's field guide: CLAUDE.md discipline, context hygiene, Explore-Plan-Code-Commit |
| P0 | [How Claude Code works in large codebases](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start) | Official | official | High | Unreviewed | Scaling across big, messy repos via CLAUDE.md layering and skills |
| P0 | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Official | official | High | Unreviewed | Duplicate — same link listed under Token efficiency § above |
| P1 | [How Anthropic teams use Claude Code](https://claude.com/blog/how-anthropic-teams-use-claude-code) | Official | official | High | Unreviewed | Internal case studies across 10 Anthropic teams |
| P1 | [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | Official | official | High | Unreviewed | Skills system and progressive disclosure design |
| P1 | [Create custom subagents](https://code.claude.com/docs/en/sub-agents) | Official | official | High | Unreviewed | Reference for building/configuring subagents with isolated context and tool scoping |
| P1 | [Hooks reference](https://code.claude.com/docs/en/hooks) | Official | official | High | Unreviewed | Lifecycle-hooks spec (PreToolUse, PostToolUse, Stop, etc.) |
| P1 | [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams) | Official | official | High | Unreviewed | Deterministic multi-agent "workflows" (fan-out/reduce/synthesize) |
| P1 | [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Official | official | High | Unreviewed | Writing effective SKILL.md descriptions and structure |
| P1 | [Codex CLI](https://developers.openai.com/codex/cli) | Official | official | Med | Unreviewed | OpenAI's official Codex CLI docs: surfaces, approval modes, sandboxing |
| P1 | [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Official | official | Med | Unreviewed | AGENTS.md hierarchy/override system for steering Codex |
| P2 | [Building Consistent Workflows with Codex CLI & Agents SDK](https://cookbook.openai.com/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk) | Official | official cookbook | Med | Unreviewed | Combining Codex CLI with the Agents SDK for repeatable pipelines |

### GitHub

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | GitHub | 50.3k stars | High | Unreviewed | Hand-curated index of skills, agents, plugins, tooling |
| P1 | [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | GitHub | 23.5k stars | High | Unreviewed | 150+ categorized production subagent definitions |

### Newsletters / podcasts

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [How Claude Code is built](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built) | Newsletter | Gergely Orosz interviewing founding engineers | High | Unreviewed | Pragmatic Engineer |
| P2 | [Head of Claude Code: what happens after coding is solved](https://www.lennysnewsletter.com/p/head-of-claude-code-what-happens) | Newsletter | interview w/ creator Boris Cherny | Med | Unreviewed | Lenny's Newsletter |
| P2 | [How to Use Claude Code Like the People Who Built It](https://every.to/podcast/how-to-use-claude-code-like-the-people-who-built-it) | Podcast | interview w/ Anthropic's Cat Wu & Boris Cherny | Med | Unreviewed | Every, Dan Shipper |

### Independent technical blogs & video

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [Simon Willison on claude-code](https://simonwillison.net/tags/claude-code/) | Blog | ongoing, high-repute independent | High | Unreviewed | Coined "designing agentic loops" / "vibe engineering" |
| P1 | [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) | Blog | 7,400-word technical teardown | High | Unreviewed | Skills internals, message injection, undocumented fields |
| P1 | [Understanding Claude Code's Full Stack: MCP, Skills, Subagents, and Hooks Explained](https://alexop.dev/posts/understanding-claude-code-full-stack/) | Blog | decision-matrix guide | High | Unreviewed | When to reach for each extensibility surface |
| P2 | [IndyDevDan — Claude Code Deep Mastery](https://www.youtube.com/playlist?list=PLS_o2ayVCKvBR3jawG9JFIzJ1vXffi8fS) | Video | 127K subscribers | Med | Unreviewed | Playlist on advanced agentic-coding patterns and context engineering |
