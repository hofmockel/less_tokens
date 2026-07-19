# Sources

Technical resources worth remembering. Add links here as found; group by topic.

## Search & retrieval

- [Keyword vs Vector vs Hybrid Search](https://medium.com/@bhdilanka/keyword-search-vs-vector-search-vs-hybrid-search-understanding-modern-information-retrieval-33b68425b295) — overview of retrieval approaches
- [Hybrid Search](https://spice.ai/learn/hybrid-search) — Spice.ai explainer

## Claude Code / Codex — token efficiency & cost

### Google

- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — official Anthropic engineering post: treat context as a finite resource, curate tokens per inference step
- [Manage costs effectively](https://code.claude.com/docs/en/costs) — official Claude Code docs on cost/token management
- [Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction) — official Anthropic platform docs on context compaction mechanics
- [Usage limit best practices](https://support.claude.com/en/articles/9797557-usage-limit-best-practices) — official Claude Help Center guidance on avoiding rate limits
- [Lessons from building Claude Code: Prompt caching is everything](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything) — official Anthropic blog on caching as the core cost/latency lever
- [Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k](https://news.ycombinator.com/item?id=48883275) — measured baseline token overhead comparison; 704 HN points
- [Universal Claude.md – cut Claude output tokens](https://news.ycombinator.com/item?id=47581701) — technique for trimming CLAUDE.md to cut output verbosity; 471 HN points
- [Show HN: CodeBurn – Analyze Claude Code token usage by task](https://news.ycombinator.com/item?id=47759035) — tool classifying session transcripts into 13 task categories; 112 HN points
- [Excessive token usage in Claude Code](https://news.ycombinator.com/item?id=47096937) — community diagnosis of token-bloat causes; 62 HN points
- [Rtk – reduce Claude Code token usage](https://news.ycombinator.com/item?id=47189599) — launch thread for a CLI-output-filtering proxy; 18 HN points
- [Tips on how to minimize Codex usage?](https://community.openai.com/t/tips-on-how-to-minimize-codex-usage/1384019) — official OpenAI Developer Community thread with concrete tips
- [How I Cut My Claude Code Token Usage by 60% and Got Better Output](https://dev.to/numbpill3d/how-i-cut-my-claude-code-token-usage-by-60-and-got-better-output-48b0) — dev.to practitioner write-up with before/after numbers
- [Cut Claude Code's token overhead by 44%](https://dev.to/harivenkatakrishnakotha/how-i-cut-claude-codes-token-overhead-by-44-and-stopped-hitting-usage-limits-mid-session-3fkf) — dev.to write-up on stopping mid-session usage-limit hits
- [10 Tips to Stop Burning Your Tokens in Claude Code](https://medium.com/@habib23me/10-tip-to-stop-burning-your-tokens-in-claude-code-4776d4ac8956) — Medium practitioner guide
- [7 Ways to Cut Your Claude Code Token Usage](https://dev.to/boucle2026/7-ways-to-cut-your-claude-code-token-usage-elb) — dev.to guide
- [12 Ways to Cut Token Consumption in Claude Code](https://www.firecrawl.dev/blog/claude-code-token-efficiency) — Firecrawl blog with specific numbers (91.9% CLAUDE.md reduction, 85.5% via .claudeignore, etc.)
- [7 Practical Ways to Reduce Claude Code Token Usage](https://www.kdnuggets.com/7-practical-ways-to-reduce-claude-code-token-usage) — established data/ML publication (KDnuggets)
- [How I Cut Claude Code Token Usage by 90%+ With 5 Tools, Custom Hooks, and Enforcement](https://medium.com/@abdulgafoorabid/how-i-cut-claude-code-token-usage-by-90-with-4-tools-custom-hooks-and-enforcement-d3f8d2488cd6) — stacks Codebase Memory MCP + context-mode + RTK + Headroom + Caveman
- [How to Reduce Codex CLI & OpenAI API Token Costs](https://inventivehq.com/knowledge-base/openai/how-to-reduce-api-token-costs) — session/context/caching/shell-filtering strategies for Codex CLI
- [Claude Code Token Optimization: 19 Changes to Cut Costs (2026)](https://buildtolaunch.substack.com/p/claude-code-token-optimization) — Substack piece reporting 40-70% savings
- [Why Claude Code Subagents Burn So Many Tokens](https://youcanbuildthings.com/articles/claude-code-subagents-token-usage/) — explains subagents as independently-billed isolated context windows, `CLAUDE_CODE_SUBAGENT_MODEL` gotcha
- [Optimise token usage in Claude Code](https://menetray.com/en/blog/how-optimise-token-usage-claude-code-without-burning-through-your-subscription) — blog post on subscription-friendly usage habits

### GitHub

- [ccusage/ccusage](https://github.com/ccusage/ccusage) — CLI for analyzing Claude Code/Codex usage from local JSONL files; 17.3k stars, 739 forks
- [anthropics/claude-code issue #49048](https://github.com/anthropics/claude-code/issues/49048) — feature request on the official repo for built-in token optimization
- [openai/codex issue #19001](https://github.com/openai/codex/issues/19001) — proposal to add RTK-style shell-output filtering directly into Codex CLI
- [openai/codex issue #14879](https://github.com/openai/codex/issues/14879) — proposal to reduce token usage for verbose `exec_command` outputs
- [openai/codex issue #5085](https://github.com/openai/codex/issues/5085) — cost tracking & usage analytics feature request on the official OpenAI Codex repo
- [rtk-ai/rtk](https://github.com/rtk-ai/rtk) — Rust CLI proxy filtering/compressing dev command output for 60-90% reduction; 71.7k stars (note: low subscriber count relative to stars — some skepticism warranted, but corroborated by independent HN/LinkedIn mentions)
- [steipete/codexbar](https://github.com/steipete/codexbar) — macOS menu bar app showing usage/limits across 63+ providers incl. Codex and Claude Code; 18.6k stars
- [davila7/claude-code-templates](https://github.com/davila7/claude-code-templates) — CLI + local analytics dashboard breaking down input/output/cache tokens and cost per session; 29.7k stars
- [Maciek-roboblog/Claude-Code-Usage-Monitor](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor) — real-time terminal monitor with burn-rate predictions; 8.5k stars
- [Kilo-Org/kilocode discussion #5848](https://github.com/Kilo-Org/kilocode/discussions/5848) — "I saved 10M tokens (89%) on my Claude Code sessions with a CLI proxy" write-up
- [junhoyeo/tokscale](https://github.com/junhoyeo/tokscale) — Rust CLI + dashboard tracking token usage/cost across 40+ coding agents; 4.5k stars
- [drona23/claude-token-efficient](https://github.com/drona23/claude-token-efficient) — single drop-in CLAUDE.md cutting output verbosity, no code changes; 5.8k stars
- [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) — curated toolkit incl. a cost-mode skill claiming 30-70% savings; 2.3k stars
- [alexgreensh/token-optimizer](https://github.com/alexgreensh/token-optimizer) — finds "ghost tokens": bloated configs, stale memory, compaction loss, model misrouting; 1.7k stars
- [mm7894215/TokenTracker](https://github.com/mm7894215/TokenTracker) — local-first token/cost tracker across 27 coding tools; 1,038 stars
- [nadimtuhin/claude-token-optimizer](https://github.com/nadimtuhin/claude-token-optimizer) — hooks-based optimizer with a concrete case (11,000 → 1,300 tokens); 526 stars
- [ooples/token-optimizer-mcp](https://github.com/ooples/token-optimizer-mcp) — MCP server, 65 tools + 7-phase hook system, claims 60-90%+ reduction via caching/compression; 442 stars
- [edouard-claude/snip](https://github.com/edouard-claude/snip) — Go CLI proxy (RTK alternative), declarative YAML filters, 60-90% reduction claim; 373 stars
- [mag123c/toktrack](https://github.com/mag123c/toktrack) — ultra-fast Rust token/cost tracker for Claude Code and others; 179 stars
- [Dicklesworthstone/coding_agent_usage_tracker](https://github.com/Dicklesworthstone/coding_agent_usage_tracker) — Rust port of CodexBar's core logic across Codex/Claude/Gemini/Cursor/Copilot; 74 stars

### LinkedIn

- [I keep hitting the Claude Code usage limit. So I built Claude Spend...](https://www.linkedin.com/posts/writetoaniketparihar_i-keep-hitting-the-claude-code-usage-limit-activity-7431248823735279617-rRZO) — founder builds a token-analytics tool after hitting limits; 155 comments
- [We heard you wanted to use Codex rate limit resets on your own time...](https://www.linkedin.com/posts/openai_we-heard-you-wanted-to-use-codex-rate-limit-activity-7470991162825277441-LbqE) — official OpenAI account announcing bankable rate-limit resets; 67 comments
- [Claude has brought compacting into chats. Here's why this is a big deal.](https://www.linkedin.com/posts/darren-coxon_claude-has-brought-compacting-into-chats-activity-7407339411639672832-6gqA) — practitioner explainer on auto-compaction mechanics
- [Anthropic Subsidies Tighten, WOZCODE Boosts Claude Efficiency](https://www.linkedin.com/posts/bentcollins_last-month-a-single-claude-user-consumed-activity-7444448271575515136-DFlZ) — Ben Collins on a user consuming ~$27k of API compute on a $200/mo plan
- [TOON Cuts Claude Code Costs by 30-60%](https://www.linkedin.com/posts/agenisea_feature-request-add-toon-token-oriented-activity-7409696865576771585-ykHF) — Token-Oriented Object Notation cutting config-file token usage
- [Manage Claude Code tokens with ccusage: A simple solution](https://www.linkedin.com/posts/groyse_claude-code-is-great-until-you-smack-into-activity-7369119700938596355-Hfsd) — practitioner walkthrough of the ccusage CLI tool
- [5 Habits to Cut Your Claude Token Use](https://www.linkedin.com/posts/analytics-vidhya_5-habits-to-cut-your-claude-token-use-by-activity-7444718907883646977-ZgXf) — official Analytics Vidhya publication account
- [Optimize Claude Code with Opus 4.6 Effort Settings](https://www.linkedin.com/posts/akashm_claude-code-tip-for-all-those-who-are-loving-activity-7427307856330366976-T_96) — adjusting model "effort" levels to cut token burn
- [How I optimized Claude Code's token usage with a custom...](https://www.linkedin.com/posts/jamiejferguson_when-i-first-started-using-claude-code-he-activity-7392297798127243264-eJVS) — custom-workflow optimization story
- [7 Ways to Reduce Claude Code Token Consumption](https://www.linkedin.com/posts/wtsorg_claude-code-bill-is-probably-high-for-the-activity-7459857488188747776-Q9wB) — practitioner list post
- [5 Claude Quick Tips to Avoid Chat Token Limit](https://www.linkedin.com/posts/derekaweber_5-claude-quick-tips-for-if-you-are-running-activity-7376340791394410496-xKaa) — quick-tip format
- [How to avoid token limits with Claude Code and Subagents](https://www.linkedin.com/posts/andrew-ansley-marketing_do-you-run-out-of-tokens-in-your-context-activity-7361978039875899393-j--J) — subagent-based context-limit avoidance technique
- [Free Claude Code Dashboard for Token Visibility](https://www.linkedin.com/posts/nateherkelman_most-people-hit-claude-code-session-limits-activity-7452096646407962624-ImDt) — free dashboard tool for session limits
- [Claude Setup Token for Long-Lived Auth](https://www.linkedin.com/posts/robert-claus-46491364_i-just-learned-about-claude-setup-token-activity-7446940848937865216-jeg-) — `claude setup-token` for CI/CD cost-relevant auth handling
- [How to find daily/monthly token usage with Claude Code Tips](https://www.linkedin.com/posts/shajeelafzal_claudecode-vibecoding-activity-7360934444255318017-lgK0) — practitioner tips post
- [Optimize Claude Usage to Avoid Token Limit](https://www.linkedin.com/posts/michaelzick_ive-been-burning-through-my-claude-limit-activity-7446364814270013441-E49h) — personal war story
- [How to Use /compact Command in Claude Code for Task Switching](https://www.linkedin.com/posts/kylemickey_how-to-switch-between-tasks-in-claude-code-activity-7392963357160501248-6Ngk) — concrete `/compact` workflow
- [Clear vs Compact in Claude Code: Best Practices](https://www.linkedin.com/posts/jdfiscus_claudecode-bestpractices-activity-7415388135443865600-rRS5) — comparing `/clear` vs `/compact` use cases
- [How to use Claude Code effectively: Providing context for...](https://www.linkedin.com/posts/markshust_one-of-the-biggest-mistakes-i-see-with-claude-activity-7392184912155435009-mixa) — the biggest context-provision mistake developers make
- [RTK Rust Token Killer: 85% menos tokens no Claude Code](https://pt.linkedin.com/pulse/rtk-como-cortei-85-do-consumo-de-tokens-claude-code-witalo-rebou%C3%A7as-utckf) — Portuguese-language Pulse article reporting an 85% token-usage cut using RTK

## Claude Code / Codex — mastery & advanced workflows

### Official / vendor

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices) — Anthropic's own field guide: CLAUDE.md discipline, context hygiene, Explore-Plan-Code-Commit
- [How Claude Code works in large codebases](https://claude.com/blog/how-claude-code-works-in-large-codebases-best-practices-and-where-to-start) — scaling Claude Code across big, messy repos via CLAUDE.md layering and skills
- [How Anthropic teams use Claude Code](https://claude.com/blog/how-anthropic-teams-use-claude-code) — internal case studies across 10 Anthropic teams
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — defines context engineering, compaction, just-in-time retrieval
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — Skills system and progressive disclosure design
- [Create custom subagents](https://code.claude.com/docs/en/sub-agents) — official reference for building/configuring subagents with isolated context and tool scoping
- [Hooks reference](https://code.claude.com/docs/en/hooks) — official lifecycle-hooks spec (PreToolUse, PostToolUse, Stop, etc.)
- [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams) — deterministic multi-agent "workflows" (fan-out/reduce/synthesize patterns)
- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — writing effective SKILL.md descriptions and structure
- [Codex CLI](https://developers.openai.com/codex/cli) — OpenAI's official Codex CLI docs: surfaces, approval modes, sandboxing, session management
- [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md) — the AGENTS.md hierarchy/override system for steering Codex
- [Building Consistent Workflows with Codex CLI & Agents SDK](https://cookbook.openai.com/examples/codex/codex_mcp_agents_sdk/building_consistent_workflows_codex_cli_agents_sdk) — combining Codex CLI with the Agents SDK for repeatable pipelines

### GitHub

- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — hand-curated index of skills, agents, plugins, tooling; 50.3k stars
- [awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) — 150+ categorized production subagent definitions; 23.5k stars

### Newsletters / podcasts

- [How Claude Code is built](https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built) — Gergely Orosz's Pragmatic Engineer interviewing Claude Code's founding engineers
- [Head of Claude Code: what happens after coding is solved](https://www.lennysnewsletter.com/p/head-of-claude-code-what-happens) — Lenny's Newsletter interview with creator Boris Cherny
- [How to Use Claude Code Like the People Who Built It](https://every.to/podcast/how-to-use-claude-code-like-the-people-who-built-it) — Every's Dan Shipper interviewing Anthropic's Cat Wu and Boris Cherny

### Independent technical blogs & video

- [Simon Willison on claude-code](https://simonwillison.net/tags/claude-code/) — ongoing dispatches; coined "designing agentic loops" / "vibe engineering" distinction
- [Claude Agent Skills: A First Principles Deep Dive](https://leehanchung.github.io/blogs/2025/10/26/claude-skills-deep-dive/) — 7,400-word technical teardown of Skills internals, message injection, undocumented fields
- [Understanding Claude Code's Full Stack: MCP, Skills, Subagents, and Hooks Explained](https://alexop.dev/posts/understanding-claude-code-full-stack/) — decision-matrix guide for when to reach for each extensibility surface
- [IndyDevDan — Claude Code Deep Mastery](https://www.youtube.com/playlist?list=PLS_o2ayVCKvBR3jawG9JFIzJ1vXffi8fS) — 127K-subscriber channel playlist on advanced agentic-coding patterns and context engineering
