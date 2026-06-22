**Bottom line:** the most impactful token-reduction method is **context selection before the model call**: send only the few pieces of information needed for the current task, usually via retrieval, filtering, reranking, and hard token budgets. Compression helps, but the biggest win is avoiding irrelevant context entirely.

**Ranked by likely impact**

1. **Retrieve less, but better**
   Use semantic search/RAG, metadata filters, score thresholds, and reranking so the model sees only top relevant chunks. OpenAI's retrieval docs note you can cap returned results with `max_num_results`, use attribute filters, and raise `score_threshold` to limit results to more relevant chunks. This is usually the biggest lever because it can turn "entire docs/codebase/history" into "3-10 chunks." Source: [OpenAI Retrieval docs](https://developers.openai.com/api/docs/guides/retrieval)

2. **Conversation/context pruning**
   For long-running chats or agents, do not keep appending the full transcript. Keep durable state: task goals, decisions, constraints, file references, current plan, unresolved questions. Drop dead branches, repeated tool output, old logs, and verbose intermediate reasoning. OpenAI's conversation-state docs explicitly warn that even `previous_response_id` still bills previous input tokens in the response chain, so state management still matters. Source: [OpenAI Conversation State docs](https://developers.openai.com/api/docs/guides/conversation-state)

3. **Prompt caching for repeated prefixes**
   This does not reduce logical prompt size, but it can massively reduce cost/latency for repeated system prompts, tool schemas, examples, and stable documents. OpenAI says prompt caching can reduce latency by up to 80% and input token costs by up to 90%, with exact prefix matching and static content placed first. Source: [OpenAI Prompt Caching docs](https://developers.openai.com/api/docs/guides/prompt-caching)

4. **Prompt compression**
   Tools like LLMLingua/LLMLingua-2 remove low-value tokens from prompts. The original LLMLingua paper reports up to 20x compression with little performance loss in some settings, while LLMLingua-2 reports 2x-5x compression and 1.6x-2.9x end-to-end latency acceleration. But newer real-world evaluation found benefits are workload-dependent: LLMLingua achieved up to 18% end-to-end speedups only when prompt length, compression ratio, and hardware matched well. Sources: [LLMLingua](https://arxiv.org/abs/2310.05736), [LLMLingua-2](https://arxiv.org/abs/2403.12968), [Prompt Compression in the Wild](https://arxiv.org/abs/2604.02985)

5. **Template and schema trimming**
   Shorten system prompts, remove redundant examples, compress tool schemas, use concise field names where safe, and avoid repeating policy/instructions every turn unless they are cacheable. This is good hygiene, but usually smaller than retrieval/pruning unless your tool schemas or system prompts are enormous.

**Recommendation**

Build the reduction strategy around a **token budgeter + relevance gate**. For every request, decide the max context budget, retrieve/filter/rerank into that budget, summarize or compact conversation state, then place stable prompt sections first to benefit from caching. That combination usually beats any single compression trick.
