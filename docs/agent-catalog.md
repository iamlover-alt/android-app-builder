# Android App Builder: Complete Agent Catalog (bottom to top)

As of 2026-10-30. Live doc: https://claude.ai/artifact/KRMXM9MWDq9Jdz5aMTy35k

## Result

The builder needs 94 roles: 8 layers that stack from sandboxes at the bottom to product strategy at the top, plus governance and orchestration that cut across all of them. The [first architecture doc](https://claude.ai/artifact/UDWP3SvsTDYC2BxE3pnofh) had 20 agents; every one is still here, usually split into smaller roles. This catalog adds backend, design, audio, 22 test and review roles, legal and safety, and failure analysis.

Not all 94 should be free-roaming LLM agents. A study of 1,642 traces from seven multi-agent frameworks found 14 failure modes, with [system design problems the largest group at 44.2%](https://www.antoinebuteau.com/multi-agent-systems-fail-like-organizations/), so more agents do not by themselves add reliability. Each role is marked **A** (LLM agent), **T** (deterministic tool with a thin agent wrapper) or **H** (hybrid).

Three rules hold everywhere:

1. **Every maker has a deterministic verifier** (compiler, test runner, linter, scanner) that it cannot talk its way past. A 2026 literature review found [Planner-Executor-Reviewer is the dominant pattern, with the reviewer providing verifiability through executable feedback](https://fugumt.com/fugumt/paper_check/2605.15245v1).
2. **Critics get tools the maker lacks**, such as a device, a scanner or the approved design, so a critic's "no" always carries evidence.
3. **Every run is traced and failures are labeled**, so the Failure Analyst can fix a role, a prompt or a tool instead of retrying blindly.

## The stack at a glance

*Diagram (not exported from the live doc):* 8 stacked layers from Foundation (bottom) to Product and discovery (top), with Governance beside every layer and Orchestration above all.

Each layer builds on the one below it. Work flows down from product intent while verification flows up from the device; governance and orchestration touch every layer.

## Layer 1 · Foundation and platform (6 roles)

These six roles give every other agent a reproducible build, a place to run it and a meter on what it costs. Most are tools, because nothing here needs judgment.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Sandbox and Environment** | T | Provisions one container per project with JDK, Android SDK, emulator images and a warm Gradle cache; restricts network access to approved package registries | Image digest, egress policy | Any build reproduces from the image digest alone |
| **Build and Dependency** | H | Owns Gradle files, the version catalog, AGP, Kotlin and Compose version compatibility, and R8 rules; fixes build errors with the smallest patch after checking failure memory | Build files, lockfile, patches | Clean build on CI; no unpinned version |
| **CI/CD Pipeline** | T | Runs build, lint, tests, screenshot tests and benchmarks on every change; caches and publishes artifacts | Pipeline definition, run records | Every merge has a green run record |
| **Device Farm** | T | Schedules emulators and real devices by API level, screen size, locale and RAM; resets state between runs; records video and logs | Device matrix, run videos | Requested matrix is available and clean |
| **Secrets and Signing** | T | Keeps keystores and API keys in a vault and exposes a signing service, so agents never see raw keys | Signed artifacts, access log | No key material in any prompt, repo or log; scanner clean |
| **Cost and Observability** | H | Meters tokens, compute and device minutes per task; traces every tool call; stops runaway loops | Cost ledger, trace store | Per-app budget enforced; traces queryable by task |

The design lesson for all agent tools comes from [SWE-agent](https://arxiv.org/abs/2405.15793v2): a purpose-built agent-computer interface beat a shell-only agent by [64% relative on SWE-bench Lite](https://hyper.ai/ar/papers/2405.15793), mainly through an edit command that lints and rejects bad edits. Build and Dependency should ship the same guardrails for Gradle and Kotlin.

## Layer 2 · Backend and data (8 roles)

Contracts come first: the API schema is written before either side, so the Android client and the server cannot drift.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Backend Architect** | A | Chooses a managed backend or a custom service from the PRD's needs for offline use, scale and data residency; records lock-in and exit cost | Backend ADR, service map | Every PRD feature has an owning service |
| **API Contract** | H | Writes the OpenAPI or GraphQL schema first; generates typed Kotlin clients, server stubs and a mock server for UI work; versions the API | Schema, generated clients, mock | Client and server compile from one schema; breaking-change check passes |
| **Data Model and Database** | H | Designs server schema, indexes, migrations and retention; sets conflict rules for offline sync with the Local Data engineer | Schema, migrations, sync contract | Migrations replay from empty; conflict cases tested |
| **Auth and Identity** | H | Sign-in (passkeys, Google sign-in), sessions, roles and the account-deletion flow | Auth config, deletion endpoint | Login, refresh, revoke and delete paths tested |
| **Cloud Infrastructure** | T | Infrastructure as code for dev, staging and production; secrets wiring, backups, autoscaling, cost alarms | IaC, environment URLs | Staging rebuilds from code; restore drill passes |
| **Messaging and Notifications** | H | Sets up push, notification channels and the runtime notification permission; quiet hours and de-duplication | Channels, server sender | Opt-out works; no notification without a channel |
| **Analytics and Experimentation** | H | Event taxonomy tied to PRD goals, privacy-safe collection, feature flags and A/B hooks | Event spec, dashboards, flags | Every PRD metric has an event; consent respected |
| **Payments and Entitlements** | H | Play Billing integration, server-side purchase validation, entitlement sync and refunds | Billing module, entitlement service | Purchase, restore, refund and expiry tested in sandbox |

Two points to verify against current Play text before shipping: account-deletion requirements for apps that create accounts, and server-side validation rules for Play Billing. Both are from general platform practice, not from the sources opened for this doc.

## Layer 3 · Android engineering (13 roles)

Thirteen roles, split by the parts of Android that fail differently: UI, lifecycle, hardware, offline data and platform change.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Android Architect** | A | Picks module graph, UI, domain and data layers, DI and state management; sets min and target SDK; writes architecture lint rules | Module graph, ADRs, lint rules | Skeleton builds; rules enforced in CI |
| **Domain Logic Engineer** | A | Use cases, ViewModels, state machines, validation and the error model | Domain modules, unit tests | Acceptance criteria that touch logic pass |
| **Compose UI Engineer** | A | Builds screens from design specs and tokens; previews for every state; no hard-coded strings or colors | Screen code, previews | Visual diff within threshold; empty, loading and error previews exist |
| **Adaptive Navigation Engineer** | H | Window size classes, list-detail panes, navigation bar or rail, foldable postures, predictive back, edge-to-edge insets | Navigation graph, adaptive scaffolds | No layout breaks from compact to expanded widths |
| **Local Data and Offline Engineer** | A | Room schema and migrations, DataStore, repository caching, sync queue and conflict handling | Local data module, migration tests | Airplane-mode flow passes; migrations verified |
| **Background Work and Lifecycle Engineer** | A | WorkManager jobs, foreground services with correct types, alarms, process-death restore, battery limits | Workers, service declarations | Survives process death and Doze in test; wake-lock rate in budget |
| **Device Capability Engineer** | A | Camera, location, Bluetooth, NFC, sensors, health data and media; runtime permissions with rationale and denied paths | Feature modules, permission flows | Each permission has a just-in-time request and a denied-path test |
| **On-device AI Engineer** | A | Chooses on-device or cloud models; handles model download, feature status and fallback on unsupported devices | AI module, fallback path | Feature degrades gracefully with the model absent |
| **Platform Compatibility** | T | Tracks target-API deadlines, behavior changes and deprecations; runs the migration checklist | Compatibility report, patches | Meets the current Play target floor |
| **Performance Engineer** | H | Startup, jank, memory, APK size, Baseline Profiles and R8 tuning | Benchmarks, profile files | Meets the PRD budgets |
| **Accessibility Engineer** | A | Semantics, TalkBack order, contrast, touch targets, font scaling, reduced motion | Accessibility fixes | Zero blocking findings from scanner and scripted TalkBack run |
| **Localization Engineer** | H | Extracts strings and plurals, RTL mirroring, date and number formats, pseudolocale builds | Strings per locale | Pseudolocale and RTL builds render without clipping |
| **Extended Surfaces Engineer** | A | Widgets, Wear OS, Android TV, Auto, XR, shortcuts and share targets when the PRD asks for them | Surface modules | Each surface meets its own Play target floor |

**Platform facts these roles must track** (from official Android pages):

- **Target API floor.** Since 31 August 2026, new apps and updates must [target Android 16 (API 36); Wear OS and Automotive need API 35, TV and XR need API 34](https://developer.android.com/google/play/requirements/target-sdk). Existing apps need API 35 to stay available to new users on newer Android versions. The page lists an extension to 1 November 2026.
- **Android 16 behavior.** For apps targeting API 36, [edge-to-edge can no longer be opted out of, predictive back animations are on by default, and orientation, resizability and aspect-ratio limits are ignored on screens of 600dp or wider](https://developer.android.com/about/versions/16/behavior-changes-16). Adaptive Navigation and Platform Compatibility own this.
- **On-device AI.** [ML Kit GenAI APIs on Gemini Nano](https://android-developers.googleblog.com/2025/05/on-device-gen-ai-apis-ml-kit-gemini-nano.html) cover summarization, proofreading, rewriting and image description, run locally with no per-call cost, and only on supported devices. The On-device AI Engineer must always ship a fallback.

## Layer 4 · Design (9 roles)

Design is split so that taste, system and consistency are owned separately; a design critic checks the built app against the approved design on a real device.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **UX Research and Persona** | A | Builds personas, jobs to be done and usability risks from the PRD and competitor teardown | Personas, JTBD, risk list | Each persona maps to at least one story; assumptions marked testable |
| **Flow and Information Architecture** | A | Screen inventory, navigation graph and every state: empty, loading, error, offline, permission denied | Nav graph, state tables | Every story reaches a screen path; no dead ends |
| **UI Design** | A | Layouts for compact, medium and expanded widths; renders previews; ingests screenshots or Figma | Screen specs, mock renders | User approves previews at the design gate |
| **Design System** | H | Material 3 theme, dynamic color, type scale, shapes, spacing and component catalog, as code tokens | Theme code, token file, catalog | Components cover all screens; contrast passes |
| **Motion Design** | A | Transitions, shared elements, loading and success animations, with reduced-motion variants | Motion spec, animation code | Stays smooth in the benchmark; reduced motion respected |
| **Icon and Illustration** | A | Adaptive launcher icon with a monochrome layer, empty-state art, onboarding illustrations, store icon | Vector assets | Renders at all densities and in themed-icon mode; no third-party marks |
| **Brand and Naming** | A | Name candidates, tone of voice and palette seeds; pre-checks trademarks with Legal | Brand brief | Name passes trademark screen and Play title rules |
| **UX Writing** | A | Microcopy, error text, permission rationales, onboarding and store tone | Copy deck keyed to string IDs | All strings externalized; tone and reading-level checks pass |
| **Design QA** (critic) | H | Compares device renders with the approved design; flags spacing, color and missing states | Visual diff report | Drift under threshold on every screen |

Tooling that exists today: Android Studio can [generate Compose code from a screenshot and connect to remote MCP servers such as Figma](https://android-developers.googleblog.com/2026/01/llm-flexibility-agent-mode-improvements.html), and the Material [adaptive layout components](https://goo.gle/483SAT0) (list-detail panes, navigation suite) cover the compact-to-expanded behavior the UI Design agent should target.

## Layer 5 · Audio and media (8 roles)

Sound gets its own layer because it has its own failure modes: clashing loops, loudness jumps, ignored audio focus and, above all, unclear rights to the music.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Audio Director** | A | Defines the sound identity: mood words, instrumentation palette, loudness targets and where silence is the right choice | Audio bible | Every screen and state has a sound decision, including "silent" |
| **Music Composition** | A | Maps app or game states (onboarding, focus, success, tension) to loops, stems and stingers; fixes tempo and key so layers crossfade; generates many variants and keeps the best | Loop and stem pack, transition rules | Loops are seamless; layers combine without clashing |
| **SFX and UI Sound** | A | Taps, success, error, notification and ambient sounds as one consistent family | SFX bank, event-to-sound map | Consistent loudness, no clipping, every event mapped in code |
| **Haptics Designer** | A | Haptic language tied to events (confirm, error, scrub) with fallbacks for devices without rich haptics | Haptic patterns, fallback map | Verified on devices with and without rich haptic support |
| **Voice and Narration** | A | Speech for guidance, onboarding and accessibility cues in several languages; handles consent for any cloned voice | Voice assets, scripts, transcripts | Consent record for every cloned voice; transcripts available |
| **Audio Integration Engineer** | H | Player design: audio focus, ducking under calls and navigation, background playback rules, preloading, memory and silent-mode behavior | Audio module, config | Interruption by a call resumes cleanly; no leaks; silent mode respected |
| **Audio Rights and Provenance** | H | Keeps a license ledger per asset: tool, model version, plan tier, date, prompt and commercial terms; holds a swap plan | Rights ledger | Every shipped audio file has a ledger row with commercial-use terms |
| **Store Media Producer** | A | Screenshots, feature graphic and promo video with licensed music and captions, localized | Store asset set | Meets Play format rules; matches the current UI |

**How the soundtrack agents should work.** [Adaptive music starts by listing every emotional state](https://medium.com/@musicarthub.com/adaptive-game-music-ai-tools-5e70be18991c) in the product and generating audio per state. Practitioners advise [generating about ten candidates and keeping two](https://relishgames.com/journal/ai-generated-music-for-indie-games-top-tools-of-2026/), and note that AI does better on short, constrained sound effects than on long music. Audio Director therefore sets the state map once; Music Composition generates against it; Audio QA (Layer 6) checks the seams.

**Rights are the least settled part of this layer.** As of a [June 2026 licensing review](https://blog.dubspot.com/ai-music-licensing-explained-2026): Suno's free tier is personal and non-commercial, with commercial rights on paid plans; Udio settled with UMG in October 2025 and Suno with Warner in November 2025; Sony was still litigating against both. ElevenLabs states its music model was [trained on licensed content, with commercial use on paid plans except film, TV and large studio games](https://metavert.io/compare/udio-vs-elevenlabs). Rule: log the plan tier on the generation date for every file, prefer providers with licensed training data for store-facing apps, and keep a path to swap in human-composed audio. Terms change often, so Rights must re-check provider terms before each release; a human lawyer decides anything beyond the ledger.

Platform practice for Audio Integration (general Android knowledge, not from the sources above): short effects through a low-latency pool, long music through a streaming player, audio focus on every playback start, and a haptics fallback chain.

## Layer 6 · Testing and review (22 roles)

Twenty-two roles in two groups: fifteen that run the app and measure it, and seven that review, audit or gate. The split follows the research: a deterministic check cannot be fooled, while an LLM reviewer [often checks surface conditions such as "it compiles" and misses whether the task was met](https://www.antoinebuteau.com/multi-agent-systems-fail-like-organizations/).

### Testers: they run the app and measure

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Requirements Verifier** | T | Links every acceptance criterion to a test and its latest result; flags uncovered criteria | Traceability matrix | Every criterion has a passing test or a signed waiver |
| **Unit Test Engineer** | A | Pure-logic tests, fakes, property tests, coroutine and Flow tests | Unit suite | Passes; meets the PRD coverage target |
| **Integration and Contract Tester** | H | Database, repository and API contract tests against the mock and staging backend | Integration suite | Contract tests pass; no schema drift |
| **UI Journey Tester** | H | Runs user journeys written in plain language through screenshots and the UI tree, with deterministic scripts as the CI fallback | Journey files, scripts | Every primary story has a journey passing on the matrix |
| **Exploratory Persona Tester** | A | Acts as a user with a persona and goals, invents its own tasks, and hunts crashes and dead ends | Bug reports with video and repro steps | No new crash or dead end within the agreed session budget |
| **Visual Regression Tester** | T | Screenshot tests per state, size, theme and font scale | Baselines, diffs | No unapproved diffs |
| **Accessibility Tester** | H | Automated scanner plus a scripted TalkBack, switch-access, large-font and color-blind pass | Accessibility report | Zero blocking findings |
| **Performance and Battery Tester** | T | Startup, jank, memory, wake locks and ANR watchdog against PRD budgets and Play thresholds | Performance report | Within budget |
| **Compatibility Matrix Tester** | T | Runs journeys across API levels, screen sizes, foldables, OEM skins, low RAM and locales | Matrix result | No device class below the pass bar |
| **Network and Fault Injection Tester** | T | Offline, slow, flaky and captive-portal networks; server 5xx; expired token; low storage; process death; permission revoked mid-flow | Fault report | Graceful recovery from every injected fault |
| **Security Tester** | H | Static and dynamic mobile security checks: exported components, cleartext traffic, WebView, deep-link hijack, plus backend endpoint probes | Findings | Zero high-severity findings |
| **Privacy Auditor** | H | Watches real network traffic and SDK behavior and compares it with the declared data-safety answers | Data-flow diff | Declared data equals observed data |
| **Localization Tester** | T | Pseudolocale, RTL, long strings, number and date formats, locale keyboards | Localization report | No clipping or untranslated strings |
| **Audio and Haptics QA** | H | Measures loudness and clipping, loop seams, audio focus, ducking, silent mode and haptic fallbacks | Audio QA report | Loudness within targets; interruptions recover |
| **Flake and Triage** | H | Reruns and clusters failures, separates real bugs from flakes, quarantines flaky tests with an expiry | Triage board | Flake rate tracked; quarantines expire |

### Reviewers and gates: they judge, audit and block

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Code Reviewer** (critic) | A | Reviews diffs for correctness, readability, concurrency and lifecycle leaks; may block only with evidence | Review verdicts | Approved with no unresolved blocker |
| **Architecture Conformance Reviewer** | T | Checks module boundaries, dependency rules and drift from ADRs with lint-style rules | Conformance report | No rule violations |
| **Test Quality Auditor** | H | Seeds faults and runs mutation testing to check that the tests actually catch bugs | Mutation score | Score above the bar; weak tests sent back |
| **Usability Review Panel** (critic) | A | Synthetic personas walk the app and rate clarity, friction and trust; flags where a real-user study is needed | Friction report | Top frictions fixed or accepted by a human |
| **Play Policy Pre-reviewer** (critic) | A | Simulates store review: permission justification, deceptive behavior, AI-content reporting, ads, data-safety match, target API, developer verification | Pre-review report | Zero policy blockers |
| **Safety Red-Teamer** (critic) | A | For every generative feature: jailbreaks, prompt injection, harmful output and the in-app report path | Red-team log | Report path present; blocked categories hold |
| **Release Candidate Verifier** | T | Reruns the full gate on the exact signed bundle: install, smoke test, upgrade over the previous version, size, signature, manifest diff | Gate record | All gates green on the bytes that will ship |

**Evidence behind the design**

- **Natural-language UI tests are real.** Android Studio's [Journeys](https://android-developers.googleblog.com/2026/01/llm-flexibility-agent-mode-improvements.html) turn plain-language steps into device interactions, check assertions against what is on screen, show a screenshot and reasoning per step, and run as Gradle tasks, so they can run in CI. UI Journey Tester should use this style and keep scripted fallbacks.
- **Autonomous explorers find more.** In the [DroidAgent paper](https://arxiv.org/abs/2311.08649), an LLM agent given a persona and goals reached 61% activity coverage against 51% for the best prior technique, and 317 of 374 self-created tasks were judged realistic.
- **Play already measures you.** Play's [bad-behavior thresholds](https://developer.android.com/google/play/vitals) are 1.09% user-perceived crash rate and 0.47% ANR rate overall, 8% per phone model, assessed over the last 28 days; excessive partial wake locks has a 5% overall threshold. Performance and Compatibility testers should treat these as hard budgets. Play's pre-launch report also runs your build on test devices before release.
- **A reviewer is only as good as what it can observe.** The failure-mode study recommends using real tests for software, and judging any reviewer by what it can see, what it may test and how it defines success.

## Layer 7 · Release and growth (10 roles)

Shipping is not the end: ten roles take the app through store review, staged rollout and the first maintenance cycle, and feed what they learn back to the builder.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Release Manager** | H | Versioning, changelog, app bundle build, signing through the vault, internal then closed then open tracks, rollback | Release plan, bundle, notes | Gate record green; a human approves production |
| **Store Listing and ASO** | A | Title, descriptions, keywords, localized listings and listing experiments; honest claims only | Listing pack | Passes the Policy Pre-reviewer; no misleading claims |
| **Compliance Submission** | H | Data-safety form, content rating, ads and permission declarations, target-API check, developer verification, account-deletion link | Filled forms, evidence | Forms match what the Privacy Auditor observed |
| **Rollout and Experiment** | H | Staged rollout percentages, remote flags, kill switches and A/B tests; halts on a vitals regression | Rollout controller | Auto-halt proven on a seeded regression |
| **Vitals and Crash Triage** | H | Reads Play vitals and crash reports, groups clusters, links them to commits and proposes fixes | Triage tickets | Crash and ANR rates under Play thresholds |
| **Review and Feedback Analyst** | A | Clusters store reviews and support mail into themes; drafts replies for human approval | Insight report, reply drafts | Weekly report; no reply posted without approval |
| **In-app Support** | A | Help center, contextual FAQs, consented diagnostic bundle and human escalation | Support module | Top intents resolved; escalation works |
| **Monetization** | A | Pricing, trials, subscriptions, ad placement within policy, paywall tests | Monetization plan | Entitlement tests pass; no dark patterns flagged |
| **Lifecycle and Retention** | A | Onboarding, activation events, re-engagement with frequency caps, win-back | Lifecycle plan | Caps enforced; notification opt-out rate monitored |
| **Maintenance and Upgrade** | H | Annual target-API bump, dependency updates, deprecations, regression runs and sunset plans | Upgrade pull requests | Meets each Play deadline before it arrives |

**Deadlines and rules these roles must read live, not from memory**

- **Target API.** [New apps and updates must target API 36 since 31 August 2026](https://developer.android.com/google/play/requirements/target-sdk), with an extension listed to **1 November 2026**. That date is days away, so any app still below the floor needs the extension request or an immediate upgrade.
- **Developer verification.** Apps on certified devices must come from verified developers; the requirement [was set to become mandatory in Brazil, Indonesia, Singapore and Thailand in September 2026 and to go global in 2027](https://www.bleepingcomputer.com/news/security/google-to-verify-all-android-devs-to-block-malware-on-google-play/). Unverified apps need a [slower sideload flow with a 24-hour wait](https://cybernews.com/security/google-test-sideloading-unverified-android-apps/). Compliance Submission handles registration.
- **AI-generated content.** Play's [AI-Generated Content policy](https://support.google.com/googleplay/android-developer/answer/14094294) makes developers responsible for preventing offensive output, and apps need an in-app way to [report or flag offensive AI content](https://techcrunch.com/?p=2619733). Google also advises [documenting rigorous testing, since it may ask to review it](https://au.news.yahoo.com/google-play-cracks-down-ai-161930315.html).

## Layer 8 · Product and discovery (4 roles)

The top layer decides what is worth building. It runs first in time but sits on top of the stack, because every layer below exists to deliver its decisions.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Product Strategist** | A | Interviews the user, pins down the audience and the one job the app does, and cuts scope to a first release | PRD, MVP cut line | User signs off the spec at gate 1 |
| **Research Scout** | A | Competitor teardown, library and API options with pinned versions, platform and policy limits for the app's category | Research brief, library shortlist | Every feature has a feasible path or is cut |
| **Requirements Engineer** | A | Turns the PRD into user stories, Gherkin acceptance criteria and measurable budgets for startup time, size and crash rate | Stories, Gherkin, budgets | Each criterion can be checked by a named test role |
| **Feasibility and Risk Assessor** (critic) | H | Says "not yet" early: checks each feature against platform limits, Play policy, device support, cost and rights risk before design starts | Risk register, go or no-go notes | Every high risk has an owner and a mitigation, or the feature is cut |

A [widely shared AI Studio starter prompt](https://prompts2products.substack.com/p/android) has the model ask exactly five clarifying questions, one at a time, and keep version one small. Product Strategist should work the same way, because a vague idea is the most expensive input to fix later.

## Cross-cutting · Governance and safety (7 roles)

These seven roles do not belong to one layer; they check all of them. Security, privacy, legal and audit mirror what a real company would staff; supply chain, responsible AI and the injection guard exist because agents read outside content and publish software.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Threat Modeling** | A | Abuse cases and trust boundaries per feature, including the agents' own tools | Threat model | Each high risk has a control and a test |
| **Supply Chain and License** | T | Bill of materials, known-vulnerability scan, license compatibility, package allowlist, look-alike package check | SBOM, license report | No disallowed license; no high-severity vulnerability |
| **Privacy and Data Protection** | H | Data inventory, privacy policy, consent flows, children's-data rules, retention and regional rules | Data map, policy text | Policy matches observed data; consent logged |
| **Legal and IP** | A | Trademark screen, third-party asset rights, terms of service, ownership of generated content; escalates judgment calls to a human lawyer | Legal checklist | No unresolved rights issue |
| **Responsible AI** | A | Rules for any generative feature: filters, in-app reporting, documented testing | AI safety plan, test record | Plan satisfies Play's AI-content policy |
| **Audit and Provenance** | T | Tamper-evident log of who or what changed what; signs artifacts; links every release to its spec, tests and rights ledger | Audit log | Every shipped byte traces to a task |
| **Injection and Tool-Abuse Guard** | H | Treats web pages, READMEs, Figma files and store reviews as data, never instructions; scans tool output for instruction-like text; limits tool scopes; requires a human for irreversible actions | Guard policy, alerts | Injection test set blocked; scopes enforced |

The last role matters most for this product: the builder reads outside content constantly (search results, library docs, design files, user reviews), and each is a path for hidden instructions. It also owns the rule that publishing, deleting backend data and changing permissions on a live app always wait for a human.

## Cross-cutting · Orchestration (7 roles)

The orchestration roles do no product work. They plan, remember, judge and improve the system itself, which is where the failure-mode research says most multi-agent systems break.

| Agent | Mode | What it does | Produces | Done when |
| --- | --- | --- | --- | --- |
| **Orchestrator** | H | Builds the task graph, assigns roles, enforces gates, budgets and loop limits, and escalates; does no domain work | Task graph, run log | Every task closed with evidence |
| **Planner and Decomposer** | A | Turns the PRD into work packages with acceptance criteria and risk; re-plans after failures | Work packages | Each package has an owner, inputs, outputs and a test |
| **Memory Keeper** | H | Project Graph, per-role context packs, failure memory and decision log | Indexed memory | Packs cite sources; stale facts expire |
| **Independent Evaluator** | H | Scores finished apps against a rubric and held-out tests that the makers never saw | Score card | Scores tracked for every version of the builder |
| **Human Liaison** | A | Writes decision briefs for each gate (what changed, evidence, options) and asks the fewest questions possible | Gate briefs | A human can decide from the brief alone |
| **Failure Analyst** | A | Labels traces by failure type (role, communication, verification, termination) and proposes fixes to roles, prompts or tools | Failure distribution report | Top failure type trends down release over release |
| **Tool Smith** | A | Designs and tests the agent-facing tools: compact output, lint-gated edits, error messages that tell the agent what to do next; retires tools that agents misuse | Tool specs, tests | Tool success rate up; misuse rate down |

The two roles that make the system learn are Failure Analyst and Tool Smith. The [failure-mode study](https://www.antoinebuteau.com/multi-agent-systems-fail-like-organizations/) splits failures into system design (44.2%), inter-agent misalignment (32.3%) and task verification (23.5%), and says each needs a different repair, so the Analyst must label before anyone changes a prompt. Tool Smith applies the SWE-agent finding that interface design alone moves results.

## Build order, gaps and open decisions

Do not build 94 roles at once. Five phases take the builder from a walking skeleton to a shipping, self-maintaining system, and each phase ends on a test, not a date.

| Phase | Adds | New roles | Total | Exit test |
| --- | --- | --- | --- | --- |
| **1. Walking skeleton** | Product Strategist, Research Scout, Requirements Engineer; Sandbox, Build, CI, Device Farm, Secrets; Orchestrator, Planner, Memory Keeper; Architect, Domain, Compose UI; Unit Test, UI Journey, Code Reviewer; Injection Guard | 18 | 18 | One idea becomes an app that builds, passes its own criteria and runs on an emulator |
| **2. Design and quality** | Feasibility Assessor; UX Research, Flow, UI Design, Design System, Design QA; Adaptive Navigation, Local Data, Accessibility Engineer; Requirements Verifier, Exploratory, Visual, Accessibility, Performance and Compatibility testers; Human Liaison, Cost and Observability, Audit | 18 | 36 | Screens match approved designs; accessibility, visual and device-matrix gates pass |
| **3. Real backends and devices** | Backend Architect, API Contract, Data Model, Auth, Cloud; Background Work, Device Capability, Platform Compatibility, Performance, Localization engineers; Integration, Fault, Security, Privacy, Localization, Architecture and Flake roles; Threat Modeling, Supply Chain, Privacy and Data Protection; Independent Evaluator | 21 | 57 | An app with sign-in, offline sync and a hardware feature passes fault, security and privacy gates |
| **4. Sound, polish and AI** | Motion, Icon, Brand, UX Writing; all eight audio roles; On-device AI, Extended Surfaces; Audio QA, Usability Panel, Test Quality Auditor, Red-Teamer; Messaging, Analytics, Payments; Responsible AI | 22 | 79 | An app with an original soundtrack passes audio QA and the rights audit; any AI feature passes red-teaming |
| **5. Ship and sustain** | All ten release and growth roles; Play Policy Pre-reviewer, Release Candidate Verifier; Legal and IP; Failure Analyst, Tool Smith | 15 | 94 | A signed bundle reaches the internal track with forms matching observed behavior; a seeded vitals regression halts a rollout |

**Gaps and risks**

- **Synthetic users are not users.** The Usability Review Panel and persona testers find friction, but cannot replace research with real people; the panel flags where a human study is needed.
- **Music rights are unsettled.** Provider terms and lawsuits changed several times in 2025 and 2026 and may change again. Keep the ledger and the swap path.
- **Policy moves every year.** The target-API floor rises annually and developer verification expands in 2027, so Maintenance and the Policy Pre-reviewer must read live policy pages, never memory.
- **More roles mean more handoffs.** The failure-mode research ties a large share of failures to coordination and verification, so keep typed handoffs, bounded retry loops and tool-first roles.
- **Cost.** Run only the roles a given app needs; the Cost and Observability role sets a per-app budget and the Orchestrator skips roles whose triggers do not apply, for example Audio for a utility app with no sound.
- **Scope.** This catalog covers native Kotlin and Jetpack Compose apps. Games with an engine, iOS and web need extra roles (level design, art pipeline, engine integration).

**Decisions needed from you**

1. Is the builder for non-technical idea owners, developers or both? This sets how many human gates to keep.
2. Are games in scope? They need engine, art and level roles beyond this catalog, and Android 16's large-screen rules exempt games.
3. Will it be a hosted service for other people or for your own use? Hosting adds abuse, support and legal roles.
4. Which model providers and what budget per app?

## Sources

**Opened in full for this doc**

- [Meet Google Play's target API level requirement](https://developer.android.com/google/play/requirements/target-sdk), Android Developers
- [Android vitals: core vitals and bad behavior thresholds](https://developer.android.com/google/play/vitals), Android Developers
- [LLM flexibility, Agent Mode improvements and Journeys, Android Studio Otter 3](https://android-developers.googleblog.com/2026/01/llm-flexibility-agent-mode-improvements.html), Android Developers Blog
- [Multi-agent systems fail like organizations (MAST taxonomy explainer)](https://www.antoinebuteau.com/multi-agent-systems-fail-like-organizations/), Antoine Buteau
- [AI Music Licensing Explained (2026)](https://blog.dubspot.com/ai-music-licensing-explained-2026), Dubspot, 12 June 2026

**Read as search results only (not opened; verify before relying on them)**

- [Android 16 behavior changes](https://developer.android.com/about/versions/16/behavior-changes-16)
- [On-device GenAI APIs with ML Kit and Gemini Nano](https://android-developers.googleblog.com/2025/05/on-device-gen-ai-apis-ml-kit-gemini-nano.html)
- [Google Play AI-Generated Content policy](https://support.google.com/googleplay/android-developer/answer/14094294), [TechCrunch on in-app reporting](https://techcrunch.com/?p=2619733), [Yahoo News on documenting AI testing](https://au.news.yahoo.com/google-play-cracks-down-ai-161930315.html)
- Developer verification: [BleepingComputer](https://www.bleepingcomputer.com/news/security/google-to-verify-all-android-devs-to-block-malware-on-google-play/), [Cybernews on the sideload flow](https://cybernews.com/security/google-test-sideloading-unverified-android-apps/)
- [SWE-agent paper](https://arxiv.org/abs/2405.15793v2) and [summary with the 64% figure](https://hyper.ai/ar/papers/2405.15793)
- [DroidAgent: intent-driven mobile GUI testing](https://arxiv.org/abs/2311.08649)
- [Literature review of agentic AI across the SDLC, 2026](https://fugumt.com/fugumt/paper_check/2605.15245v1)
- [MetaGPT](https://github.com/geekan/MetaGPT) and [ChatDev overview](https://www.pragmaticcoders.com/resources/ai-developer-tools), from the first doc
- Audio: [adaptive music with AI tools](https://medium.com/@musicarthub.com/adaptive-game-music-ai-tools-5e70be18991c), [AI music for indie games](https://relishgames.com/journal/ai-generated-music-for-indie-games-top-tools-of-2026/), [Udio vs ElevenLabs licensing](https://metavert.io/compare/udio-vs-elevenlabs)
- [Material adaptive layouts announcement](https://goo.gle/483SAT0) and [AI Studio starter prompt](https://prompts2products.substack.com/p/android)

Figures and dates are as of 30 October 2026. Statements marked "general Android knowledge" or "verify against current Play text" come from background knowledge, not from these sources.
