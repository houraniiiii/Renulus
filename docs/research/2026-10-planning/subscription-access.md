# Selected subscriptions — round 2 evidence

Accessed **2026-10-04**. Product selection is confirmed by the user; integration
and account access have not been exercised. This note supersedes the earlier
open-ended provider proposals. The later [architecture](../../planning/ARCHITECTURE.md)
adopts the Hermes foundation; this note remains evidence for subscription access.

| Subscription | User-approved model | Documented identifier |
| --- | --- | --- |
| Codex | GPT 6.1 Sol | gpt-6.1-sol |
| Codex | GPT 6 Astra | gpt-6-astra |
| Codex | GPT 6 Luna | gpt-6-luna |
| OpenCode Go | MiMo V2.6 Pro | mimo-v2.6-pro |
| OpenCode Go | DeepSeek V4.1 Flash | deepseek-v4.1-flash |

[Official Codex model documentation](https://learn.chatgpt.com/docs/models)
lists the three selected OpenAI names/identifiers and notes that availability
depends on plan, client and workspace settings. The allowlist is a Renulus
requirement, not proof that every connected account has all three.

[OpenCode Go documentation](https://opencode.ai/docs/go/) describes subscribing
and obtaining a Go API key. Its endpoint table includes both selected models
through the Go chat-completions endpoint. A subscription-backed key is consistent
with the user's choice; it is not a separate owner-funded inference service.
Verify current terms, account limits and file capabilities during integration.

[OpenAI's plan-usage documentation](https://developers.openai.com/siwc/token-sharing-open-source)
describes an explicit Sign in with ChatGPT flow for open-source local applications
to request eligible plan-backed Responses access. This provides a documented
integration candidate; it does not establish that Renulus is registered or that
every desired model/input is enabled for a particular user.

Engineering must choose the supported integration, protect user-provided
credentials, detect unavailable models, handle exhausted usage and preserve
unfinished work. Do not copy another app's stored authentication, silently
switch subscriptions, add models, or activate a separately billed API fallback.
No credentials, account state or model inference were accessed for this note.

Round 3 confirms automatic selection within the chosen subscription and allowed
models, with manual override and no silent subscription switching.
Provider/model availability and file capabilities are implementation checks,
not reasons to re-open the already settled subscription preference.
