# Windows app, local backend and model access

**Historical comparison, superseded after round 3.** The confirmed Hermes fork
and [consolidated architecture](../../planning/ARCHITECTURE.md) replace the WPF
proposal below. Reuse Hermes's Electron/React desktop and Python runtime.
MIT for own code and CC BY 4.0 for original teaching content are selected;
earlier licence/provider/interaction questions below describe research at that time.

Research/access date: **2026-10-04** for every linked primary source below. **Planning proposal, not an adopted architecture or implementation.** The latest user answers supersede the older cleanup-only scope.

**Round 2 update:** Codex and/or OpenCode Go subscriptions, the five-model list
and personal Windows computers are now selected. The provider/local-endpoint
alternatives below are historical research, not current requirements. Use
[selected subscription evidence](subscription-access.md) for the current
integration investigation. Desktop framework alternatives below were not adopted.

**Confirmed constraints.** Renulus serves practising EU nephrologists through specialisation: English first, optional EU languages later; brief daytime learning, focused study, cases, examinations and updates. Chat/Explain and Test are separate. Reviewed questions support scored assessment; generated questions support practice. Useful memory should avoid repetition. Windows is the only platform. The open-source application uses existing models; the owner hosts neither a service nor inference. User-and-assistant review remains required, without an external-panel prerequisite or an accuracy guarantee.

**Recommended default — engineering judgement.** Use a Windows desktop application with a small backend inside its process: **WPF on supported .NET LTS, Microsoft.Extensions.AI, a maintained provider adapter, and SQLite**. Adopt these libraries directly; build Renulus-specific learning behaviour around them. This keeps UI, storage and networking in one runtime. It needs neither Docker nor a separately administered database/web server. Framework and provider selection remain proposals.

| Approach | Verified adoption facts | Engineering assessment and Windows burden |
| --- | --- | --- |
| Reuse **Cherry Studio** | Existing Windows desktop harness with cloud/local providers, conversations and document features; community source is [AGPL-3.0](https://github.com/CherryHQ/cherry-studio). | Fastest general chat starting point. A Renulus fork inherits a broad Electron application, dependency updates and upstream merge work; assessment/programme workflows still need development. Distribution carries [corresponding-source obligations](https://github.com/CherryHQ/cherry-studio/blob/main/LICENSE). |
| Thin **WPF + Microsoft.Extensions.AI** — proposed default | [WPF](https://learn.microsoft.com/en-us/dotnet/desktop/wpf/overview/) is Windows-only; [IChatClient](https://learn.microsoft.com/en-us/dotnet/ai/microsoft-extensions-ai) supplies provider abstractions and streaming. [WPF](https://github.com/dotnet/wpf/blob/main/LICENSE.TXT) and [Extensions](https://raw.githubusercontent.com/dotnet/extensions/main/LICENSE) are MIT-licensed. | One C#/XAML application; custom learning UI remains work. Bundle .NET for easier installation, accepting larger downloads and responsibility to republish runtime patches. C# familiarity and rich-content rendering fit remain untested. |
| Thin **Electron + Vercel AI SDK** | [Electron](https://www.electronjs.org/docs/latest/) bundles Chromium/Node; the [AI SDK](https://ai-sdk.dev/docs/introduction) supplies provider integrations. Licences: [MIT](https://raw.githubusercontent.com/electron/electron/main/LICENSE), [Apache-2.0](https://raw.githubusercontent.com/vercel/ai/main/LICENSE). | Strong alternative for a TypeScript/web UI team. Ship and patch the browser/runtime; keep credentials and provider calls in the main process. Windows [updates](https://www.electronjs.org/docs/latest/tutorial/updates) need packaged releases and update metadata. Cross-platform capability adds no Renulus requirement. |

For the .NET proposal, [self-contained publishing](https://learn.microsoft.com/en-us/dotnet/core/deploying/) removes the separate .NET installation requirement but remains OS/CPU-specific and does not eliminate native prerequisites. A portable folder is a possible distribution format, not guaranteed permission to run on managed hospital machines. Propose a signed per-user installer first. Pin dependencies and preserve notices; review native/transitive packages. Renulus's own licence remains unselected; component licences do not cover teaching content.

**Model access is a separate decision.** Open-source describes application rights. Open-weight describes availability of model parameters under their own licence; it neither guarantees unrestricted reuse nor provides hardware/inference. An account identifies a user; API access or an explicitly supported subscription integration supplies model access. None follows automatically from Renulus being open-source.

Propose user-configured connection profiles: provider/endpoint, authentication and model. Data flows **Renulus on the user's PC → the chosen provider or institution endpoint → Renulus**, without an owner-operated relay. Optional loopback endpoints can reach a model runtime the user already operates; assume no GPU and bundle no model by default. Show the destination and send only relevant context, not the entire learning history. Endpoint operators' policies still apply.

A [maintained .NET adapter](https://www.nuget.org/packages/Microsoft.Extensions.AI.OpenAI) supports OpenAI-compatible endpoints; that label is not evidence that every endpoint supports identical streaming, structured outputs, tools or images. Engineers must test required capabilities per supported connection. OpenAI also documents an [official C# SDK](https://developers.openai.com/api/docs/libraries); this is an integration candidate, not a provider selection.

Do not scrape browser cookies, reuse another application's credentials or treat consumer subscriptions as generic APIs. However, current official documentation describes [ChatGPT plan access for open-source local apps](https://developers.openai.com/siwc/token-sharing-open-source) through explicit OAuth consent. Its [preview restrictions](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations) include mandatory streaming, disabled server-side response storage and unavailable hosted tools. Record this as an optional authorised-access candidate; Renulus eligibility/account availability and integration behaviour remain unverified. A normal [API connection](https://developers.openai.com/api/reference/overview) uses its documented credentials; never distribute an owner-funded shared key.

**Engineer-owned local operation proposals.** Use [Microsoft.Data.Sqlite](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/) directly for progress, attempts, saved explanations, curated memory and content-version metadata. Separate reviewed assessment items from generated practice material. SQLite itself is [public domain](https://www.sqlite.org/copyright.html); the .NET package brings [SQLitePCLRaw/native dependencies](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/custom-versions), which need their own inventory. Avoid adding an ORM or vector service until a concrete requirement justifies it.

Protect user-entered credentials with Windows [DPAPI under the current user](https://learn.microsoft.com/en-us/dotnet/standard/security/how-to-use-data-protection); keep them out of logs, learning exports and repository files. Store mutable data separately from installed binaries. Export learning data in a versioned format; require reauthentication on another PC.

Provide downloaded, rights-cleared content, reviewed questions, progress and saved explanations offline. Newly generated answers require a reachable model, local or external. Offline material should display its edition/review date; “current updates” require later retrieval and review.

Engineers own transactional schema migrations, pre-migration snapshots, restore checks and signed application/content updates. Use the [database backup API](https://learn.microsoft.com/en-us/dotnet/standard/data/sqlite/backup) rather than casually copying an active database. Keep content versions with attempts so corrections do not silently rewrite historical scores. A downloadable release/update feed does not require running a Renulus inference service. Test installation, upgrades and recovery later with synthetic data.

**Follow-up after round 2.**

The subscription/provider and personal-PC questions are closed. Engineers still
need to validate documented authentication, selected model/input availability,
usage-limit handling, supported Windows versions and processor architectures.
Offline saved-content access is proposed; offline model generation is not
selected. Round 3 subsequently confirmed automatic model choice within the
selected subscription, manual override and no silent subscription switching.
