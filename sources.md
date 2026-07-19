# Sources

Technical resources worth remembering. Add rows as found; keep the priority/status columns current so this stays a triage tool, not just a link dump.

**Priority** — P0 canonical (official, read first) · P1 high-value (verified numbers or deep technical content) · P2 useful context (anecdotal but plausible) · P3 low-signal (listicle, self-promo, redundant — skim or skip)
**Type** — Official / GitHub / Forum (HN) / Blog / Social (LinkedIn) / Newsletter-Podcast
**Signal** — the concrete evidence backing the claim: stars, HN points, comment count, or "official"/"anecdotal"/"unverified"
**Relevance** — does this map to a technique or competitor LT should track (High/Med/Low)
**Status** — Unreviewed (default) / Reviewed / Actioned / Discard — update as you triage

**Last triage: 2026-07-18** — `Actioned` rows produced `BACKLOG.md` items; `Reviewed` rows were useful but map to shipped work, an existing backlog/decision, or no distinct strategy; `Discard` rows are duplicates, tangential, or lower-signal restatements.

## Search & retrieval

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P2 | [Keyword vs Vector vs Hybrid Search](https://medium.com/@bhdilanka/keyword-search-vs-vector-search-vs-hybrid-search-understanding-modern-information-retrieval-33b68425b295) | Blog | anecdotal | Med | Actioned | HS1: benchmark lexical + vector rank fusion against vector-only search |
| P2 | [Hybrid Search](https://spice.ai/learn/hybrid-search) | Blog (vendor) | vendor explainer | Med | Actioned | HS1: exact-identifier failure mode and RRF candidate design |

## Claude Code / Codex — token efficiency & cost

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P0 | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Official | official | High | Actioned | CP1: tune compaction for critical-fact recall before precision |
| P0 | [Manage costs effectively](https://code.claude.com/docs/en/costs) | Official | official | High | Actioned | IR1, CP1, PC1: instruction scope, custom compaction, native cache usage |
| P0 | [Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction) | Official | official | High | Actioned | CP1: validate task-aware retention on versioned traces |
| P0 | [Lessons from building Claude Code: Prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) | Official | official | High | Actioned | PC1: report native cache health and evidence-backed invalidation windows |
| P1 | [Usage limit best practices](https://support.claude.com/en/articles/9797557-usage-limit-best-practices) | Official | official | Med | Reviewed | Existing compaction, context, and usage guidance |
| P1 | [Tips on how to minimize Codex usage?](https://community.openai.com/t/tips-on-how-to-minimize-codex-usage/1384019) | Official (community) | official thread | Med | Reviewed | Community advice maps to shipped context/output controls |
| P1 | [Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k](https://news.ycombinator.com/item?id=48883275) | Forum (HN) | 704 pts | High | Reviewed | Baseline supports existing fixed-context audits; no distinct mechanism |
| P1 | [Universal Claude.md – cut Claude output tokens](https://news.ycombinator.com/item?id=47581701) | Forum (HN) | 471 pts | High | Reviewed | Existing instruction pruning and terse-output strategies |
| P1 | [12 Ways to Cut Token Consumption in Claude Code](https://www.firecrawl.dev/blog/claude-code-token-efficiency) | Blog (vendor) | specific numbers (91.9%, 85.5%) | High | Reviewed | Most techniques already shipped; vendor web-fetch claims need independent payload evidence |
| P1 | [Why Claude Code Subagents Burn So Many Tokens](https://youcanbuildthings.com/articles/claude-code-subagents-token-usage/) | Blog | technical depth | High | Reviewed | Existing SA1–SA6 roadmap; model routing remains rejected as S6 |
| P2 | [Show HN: CodeBurn – Analyze Claude Code token usage by task](https://news.ycombinator.com/item?id=47759035) | Forum (HN) | 112 pts | Med | Reviewed | Existing local stats and liveness telemetry cover the actionable core |
| P2 | [Excessive token usage in Claude Code](https://news.ycombinator.com/item?id=47096937) | Forum (HN) | 62 pts | Med | Reviewed | Diagnosis maps to shipped controls |
| P2 | [How I Cut My Claude Code Token Usage by 60% and Got Better Output](https://dev.to/numbpill3d/how-i-cut-my-claude-code-token-usage-by-60-and-got-better-output-48b0) | Blog | anecdotal, before/after numbers | Med | Reviewed | Existing strategy mix; claims not independently reproducible |
| P2 | [Cut Claude Code's token overhead by 44%](https://dev.to/harivenkatakrishnakotha/how-i-cut-claude-codes-token-overhead-by-44-and-stopped-hitting-usage-limits-mid-session-3fkf) | Blog | anecdotal, numbers | Med | Reviewed | Existing instruction/context controls |
| P2 | [7 Practical Ways to Reduce Claude Code Token Usage](https://www.kdnuggets.com/7-practical-ways-to-reduce-claude-code-token-usage) | Blog (established pub) | KDnuggets | Med | Reviewed | Existing strategy mix |
| P2 | [How I Cut Claude Code Token Usage by 90%+ With 5 Tools, Custom Hooks, and Enforcement](https://medium.com/@abdulgafoorabid/how-i-cut-claude-code-token-usage-by-90-with-4-tools-custom-hooks-and-enforcement-d3f8d2488cd6) | Blog | anecdotal, concrete stack | Med | Reviewed | Search, filtering, context, and terse controls already shipped |
| P2 | [How to Reduce Codex CLI & OpenAI API Token Costs](https://inventivehq.com/knowledge-base/openai/how-to-reduce-api-token-costs) | Blog | anecdotal | Med | Reviewed | Existing Codex context/cache/output guidance |
| P2 | [Claude Code Token Optimization: 19 Changes to Cut Costs (2026)](https://buildtolaunch.substack.com/p/claude-code-token-optimization) | Newsletter | reports 40-70% savings | Med | Reviewed | Existing strategy mix; savings remain unverified |
| P3 | [Show HN: Rtk – reduce Claude Code token usage](https://news.ycombinator.com/item?id=47189599) | Forum (HN) | 18 pts | Med | Discard | Lower-signal duplicate of the RTK repository row |
| P3 | [10 Tips to Stop Burning Your Tokens in Claude Code](https://medium.com/@habib23me/10-tip-to-stop-burning-your-tokens-in-claude-code-4776d4ac8956) | Blog | unverified | Low | Discard | Generic listicle |
| P3 | [7 Ways to Cut Your Claude Code Token Usage](https://dev.to/boucle2026/7-ways-to-cut-your-claude-code-token-usage-elb) | Blog | unverified | Low | Discard | Generic listicle |
| P3 | [Optimise token usage in Claude Code](https://menetray.com/en/blog/how-optimise-token-usage-claude-code-without-burning-through-your-subscription) | Blog | anecdotal | Low | Discard | Generic usage habits; no distinct mechanism |

### GitHub (token efficiency)

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [ccusage/ccusage](https://github.com/ccusage/ccusage) | GitHub | 17.3k stars, 739 forks | High | Actioned | PC1: native cache-read/cache-write reporting is useful prior art |
| P1 | [anthropics/claude-code issue #49048](https://github.com/anthropics/claude-code/issues/49048) | GitHub (official) | official repo issue | High | Reviewed | Roadmap signal, not implementation evidence |
| P1 | [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) | GitHub | 29.7k stars | High | Actioned | PC1: per-session cache-token breakdown is useful prior art |
| P1 | [rtk-ai/rtk](https://github.com/rtk-ai/rtk) | GitHub | 71.7k stars (flagged: low subscribers relative to stars) | High | Reviewed | Existing lean-output, truncation, listing, and read guards cover the mechanism; published savings are estimates |
| P1 | [drona23/claude-token-efficient](https://github.com/drona23/claude-token-efficient) | GitHub | 5.8k stars | High | Reviewed | Existing terse-output and instruction-pruning strategies |
| P2 | [openai/codex issue #19001](https://github.com/openai/codex/issues/19001) | GitHub (official) | official repo issue | Med | Reviewed | Existing Codex output filtering; platform enforcement gaps already tracked |
| P2 | [openai/codex issue #14879](https://github.com/openai/codex/issues/14879) | GitHub (official) | official repo issue | Med | Reviewed | Existing Codex output caps; platform enforcement gaps already tracked |
| P2 | [openai/codex issue #5085](https://github.com/openai/codex/issues/5085) | GitHub (official) | official repo issue | Med | Reviewed | Existing local stats; PC1 captures the only distinct cache-health gap |
| P2 | [steipete/codexbar](https://github.com/steipete/codexbar) | GitHub | 18.6k stars | Med | Reviewed | External quota UI; no repo-level reduction strategy |
| P2 | [Maciek-roboblog/Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) | GitHub | 8.5k stars | Med | Reviewed | Burn-rate UI is adjacent to existing stats, not a token-reduction lever |
| P2 | [Kilo-Org/kilocode discussion #5848](https://github.com/Kilo-Org/kilocode/discussions/5848) | GitHub (discussion) | anecdotal, "saved 10M tokens (89%)" | Med | Reviewed | CLI filtering duplicates shipped controls; claim unverified |
| P2 | [junhoyeo/tokscale](https://github.com/junhoyeo/tokscale) | GitHub | 4.5k stars | Med | Reviewed | Cross-agent analytics duplicates local stats scope |
| P2 | [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | GitHub | 2.3k stars | Med | Reviewed | Curated bundle; no distinct verified mechanism |
| P2 | [alexgreensh/token-optimizer](https://github.com/alexgreensh/token-optimizer) | GitHub | 1.7k stars | Med | Actioned | IR1: audit hidden fixed-context sources and stale memory, not just root files |
| P2 | [nadimtuhin/claude-token-optimizer](https://github.com/nadimtuhin/claude-token-optimizer) | GitHub | 526 stars | Med | Reviewed | Hooks and config pruning duplicate shipped strategies; case study not independently verified |
| P2 | [ooples/token-optimizer-mcp](https://github.com/ooples/token-optimizer-mcp) | GitHub | 442 stars (low relative to scope claimed) | Med | Reviewed | Adds MCP schema tax and unverified breadth; no distinct validated mechanism |
| P3 | [mm7894215/TokenTracker](https://github.com/mm7894215/TokenTracker) | GitHub | 1,038 stars | Low | Discard | Generic external tracker; duplicate scope |
| P3 | [edouard-claude/snip](https://github.com/edouard-claude/snip) | GitHub | 373 stars | Low | Discard | Lower-signal RTK alternative |
| P3 | [mag123c/toktrack](https://github.com/mag123c/toktrack) | GitHub | 179 stars | Low | Discard | Generic tracker; duplicate scope |
| P3 | [Dicklesworthstone/coding_agent_usage_tracker](https://github.com/Dicklesworthstone/coding_agent_usage_tracker) | GitHub | 74 stars | Low | Discard | Low-signal port of an already-reviewed tracker |

### LinkedIn

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [We heard you wanted to use Codex rate limit resets on your own time...](https://www.linkedin.com/posts/openai_we-heard-you-wanted-to-use-codex-rate-limit-activity-7470991162825277441-LbqE) | Social | official OpenAI account | Med | Discard | Announcement: bankable rate-limit resets; provider entitlement, not a repo strategy |
| P2 | [Claude has brought compacting into chats. Here's why this is a big deal.](https://www.linkedin.com/posts/darren-coxon_claude-has-brought-compacting-into-chats-activity-7407339411639672832-6gqA) | Social | practitioner explainer | Med | Reviewed | Lower-authority restatement of official compaction guidance |
| P2 | [Anthropic Subsidies Tighten, WOZCODE Boosts Claude Efficiency](https://www.linkedin.com/posts/bentcollins_last-month-a-single-claude-user-consumed-activity-7444448271575515136-DFlZ) | Social | notable data point | Med | Reviewed | Cost motivation only; no reproducible strategy |
| P2 | [How to Use /compact Command in Claude Code for Task Switching](https://www.linkedin.com/posts/kylemickey_how-to-switch-between-tasks-in-claude-code-activity-7392963357160501248-6Ngk) | Social | practitioner | Med | Reviewed | Existing compaction strategy; CP1 uses official guidance |
| P2 | [Clear vs Compact in Claude Code: Best Practices](https://www.linkedin.com/posts/jdfiscus_claudecode-bestpractices-activity-7415388135443865600-rRS5) | Social | practitioner | Med | Reviewed | Existing compaction strategy; CP1 uses official guidance |
| P3 | [I keep hitting the Claude Code usage limit. So I built Claude Spend...](https://www.linkedin.com/posts/writetoaniketparihar_i-keep-hitting-the-claude-code-usage-limit-activity-7431248823735279617-rRZO) | Social | 155 comments, self-promo | Low | Discard | Founder builds token-analytics tool |
| P3 | [TOON Cuts Claude Code Costs by 30-60%](https://www.linkedin.com/posts/agenisea_feature-request-add-toon-token-oriented-activity-7409696865576771585-ykHF) | Social | unverified claim | Low | Discard | Token-Oriented Object Notation for config files |
| P3 | [Manage Claude Code tokens with ccusage: A simple solution](https://www.linkedin.com/posts/groyse_claude-code-is-great-until-you-smack-into-activity-7369119700938596355-Hfsd) | Social | walkthrough | Low | Discard | Redundant with ccusage GitHub entry above |
| P3 | [5 Habits to Cut Your Claude Token Use](https://www.linkedin.com/posts/analytics-vidhya_5-habits-to-cut-your-claude-token-use-by-activity-7444718907883646977-ZgXf) | Social | official account, listicle | Low | Discard | Analytics Vidhya |
| P3 | [Optimize Claude Code with Opus 4.6 Effort Settings](https://www.linkedin.com/posts/akashm_claude-code-tip-for-all-those-who-are-loving-activity-7427307856330366976-T_96) | Social | anecdotal | Low | Discard | Duplicates rejected model-routing strategy S6 |
| P3 | [How I optimized Claude Code's token usage with a custom...](https://www.linkedin.com/posts/jamiejferguson_when-i-first-started-using-claude-code-he-activity-7392297798127243264-eJVS) | Social | anecdotal | Low | Discard | Custom-workflow optimization story |
| P3 | [7 Ways to Reduce Claude Code Token Consumption](https://www.linkedin.com/posts/wtsorg_claude-code-bill-is-probably-high-for-the-activity-7459857488188747776-Q9wB) | Social | listicle | Low | Discard | Practitioner list post |
| P3 | [5 Claude Quick Tips to Avoid Chat Token Limit](https://www.linkedin.com/posts/derekaweber_5-claude-quick-tips-for-if-you-are-running-activity-7376340791394410496-xKaa) | Social | listicle | Low | Discard | Quick-tip format |
| P3 | [How to avoid token limits with Claude Code and Subagents](https://www.linkedin.com/posts/andrew-ansley-marketing_do-you-run-out-of-tokens-in-your-context-activity-7361978039875899393-j--J) | Social | anecdotal | Low | Discard | Existing evidence-gated subagent roadmap |
| P3 | [Free Claude Code Dashboard for Token Visibility](https://www.linkedin.com/posts/nateherkelman_most-people-hit-claude-code-session-limits-activity-7452096646407962624-ImDt) | Social | promo | Low | Discard | Free dashboard tool for session limits |
| P3 | [Claude Setup Token for Long-Lived Auth](https://www.linkedin.com/posts/robert-claus-46491364_i-just-learned-about-claude-setup-token-activity-7446940848937865216-jeg-) | Social | tangential | Low | Discard | `claude setup-token` for CI/CD — auth, not cost |
| P3 | [How to find daily/monthly token usage with Claude Code Tips](https://www.linkedin.com/posts/shajeelafzal_claudecode-vibecoding-activity-7360934444255318017-lgK0) | Social | anecdotal | Low | Discard | Practitioner tips post |
| P3 | [Optimize Claude Usage to Avoid Token Limit](https://www.linkedin.com/posts/michaelzick_ive-been-burning-through-my-claude-limit-activity-7446364814270013441-E49h) | Social | anecdotal | Low | Discard | Personal war story |
| P3 | [How to use Claude Code effectively: Providing context for...](https://www.linkedin.com/posts/markshust_one-of-the-biggest-mistakes-i-see-with-claude-activity-7392184912155435009-mixa) | Social | anecdotal | Low | Discard | The biggest context-provision mistake developers make |
| P3 | [RTK Rust Token Killer: 85% menos tokens no Claude Code](https://pt.linkedin.com/pulse/rtk-como-cortei-85-do-consumo-de-tokens-claude-code-witalo-rebou%C3%A7as-utckf) | Social | unverified, non-English | Low | Discard | Redundant with rtk-ai/rtk GitHub entry above |

## Claude Code / Codex — mastery & advanced workflows

### Official / vendor

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P0 | [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) | Official | official | High | Actioned | IR1 and CP1: conditional instruction loading and task-aware compaction |
| P0 | [How Claude Code works in large codebases](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start) | Official | official | High | Reviewed | Existing search-first, instruction, skill, and subagent strategies |
| P0 | [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | Official | official | High | Discard | Duplicate — actioned under Token efficiency above |
| P1 | [How Anthropic teams use Claude Code](https://claude.com/blog/how-anthropic-teams-use-claude-code) | Official | official | High | Reviewed | Case studies map to existing workflow and delegation guidance |
| P1 | [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | Official | official | High | Reviewed | Existing progressive-disclosure skill audits |
| P1 | [Create custom subagents](https://code.claude.com/docs/en/sub-agents) | Official | official | High | Reviewed | Existing SA1–SA6 roadmap; model routing remains rejected as S6 |
| P1 | [Hooks reference](https://code.claude.com/docs/en/hooks) | Official | official | High | Reviewed | Existing hook implementation and parity backlog |
| P1 | [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams) | Official | official | High | Reviewed | Existing evidence-gated delegation guidance |
| P1 | [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) | Official | official | High | Reviewed | Existing skill description/body audits and progressive disclosure |
| P1 | [Codex CLI](https://developers.openai.com/codex/cli) | Official | official | Med | Reviewed | General surface reference; no distinct token strategy |
| P1 | [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) | Official | official | Med | Actioned | IR1: model the root-to-CWD chain, overrides, and max-byte cap |
| P2 | [Building Consistent Workflows with Codex CLI & Agents SDK](https://cookbook.openai.com/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk) | Official | official cookbook | Med | Reviewed | Repeatability guidance, not a distinct token-saving mechanism |

### GitHub

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) | GitHub | 50.3k stars | High | Reviewed | Discovery index, not primary implementation evidence |
| P1 | [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) | GitHub | 23.5k stars | High | Reviewed | Definition catalog; no distinct evidence beyond existing SA roadmap |

### Newsletters / podcasts

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [How Claude Code is built](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built) | Newsletter | Gergely Orosz interviewing founding engineers | High | Reviewed | Useful architecture context; official sources cover actionable strategies |
| P2 | [Head of Claude Code: what happens after coding is solved](https://www.lennysnewsletter.com/p/head-of-claude-code-what-happens) | Newsletter | interview w/ creator Boris Cherny | Med | Reviewed | Product direction, not a distinct strategy |
| P2 | [How to Use Claude Code Like the People Who Built It](https://every.to/podcast/how-to-use-claude-code-like-the-people-who-built-it) | Podcast | interview w/ Anthropic's Cat Wu & Boris Cherny | Med | Reviewed | Workflow context maps to existing guidance |

### Independent technical blogs & video

| Priority | Source | Type | Signal | Relevance | Status | Notes |
|---|---|---|---|---|---|---|
| P1 | [Simon Willison on claude-code](https://simonwillison.net/tags/claude-code/) | Blog | ongoing, high-repute independent | High | Reviewed | Useful watch source; no single distinct finding in this triage |
| P1 | [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) | Blog | 7,400-word technical teardown | High | Reviewed | Existing skill progressive-disclosure and description audits |
| P1 | [Understanding Claude Code's Full Stack: MCP, Skills, Subagents, and Hooks Explained](https://alexop.dev/posts/understanding-claude-code-full-stack/) | Blog | decision-matrix guide | High | Reviewed | Existing surface-selection guidance and implementation |
| P2 | [IndyDevDan — Claude Code Deep Mastery](https://www.youtube.com/playlist?list=PLS_o2ayVCKvBR3jawG9JFIzJ1vXffi8fS) | Video | 127K subscribers | Med | Reviewed | Broad training material; no bounded distinct finding |
