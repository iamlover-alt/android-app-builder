# Android App Builder: Multi-Agent Architecture

As of 2026-10-30. Live doc: https://claude.ai/artifact/UDWP3SvsTDYC2BxE3pnofh

## Summary

The builder needs 20 agents in 6 squads, run by one Orchestrator over a shared, typed Project Graph instead of free chat. That pairing fixes the two failures common to earlier systems: agents losing context between roles, and code that is never actually run.

The builder takes a one-line idea (or a screenshot, a Figma file, or an existing iOS or web app) and returns a signed, tested, store-ready Kotlin and Jetpack Compose app plus its backend, privacy disclosures and listing.

Design principles:

1. **Structured handoffs, not conversation.** Every agent reads and writes typed artifacts (spec, design tokens, module graph, test report), following MetaGPT's documents-over-dialogue approach.
2. **Execution is the judge.** Nothing counts as done until Gradle builds it, tests pass, and the app runs on an emulator. Agents see compiler, lint and UI-test output directly.
3. **Agent-shaped tools.** Each agent gets a small, documented tool set with guardrails (edit-then-lint, rejected edits roll back), the main lesson of SWE-agent.
4. **Humans decide at a few gates, not every step.** Spec sign-off, design sign-off, and release are the defaults; everything else is auto-approved with a full audit trail.
5. **Native and modern by default.** Kotlin, Compose, Material 3, Hilt, Room, coroutines and Flow, and a multi-module Gradle build with version catalogs.

## Lessons from documented approaches

Each prior system solved one part well; none combined a full role pipeline with real Android execution and store release.

| Approach | What it does well | Gap this design fixes |
| --- | --- | --- |
| [MetaGPT](https://github.com/geekan/MetaGPT) | Roles (PM, Architect, Project Manager, Engineer, QA) run a software SOP and pass structured documents, not chat | Mostly greenfield Python; no device testing, no release path |
| [ChatDev](https://www.pragmaticcoders.com/resources/ai-developer-tools) | Waterfall stages (design, code, test, document) with paired reviewer and programmer agents | Free-form dialogue drifts; reviews are LLM opinion, not execution |
| [SWE-agent](https://arxiv.org/abs/2405.15793v2) | Agent-computer interface: compact commands, file viewer, lint-gated edits; beats a raw shell by 64% relative on SWE-bench Lite | Single-issue scope; weak on long multi-file work |
| [Android Studio Agent Mode](https://sdtimes.com/mobile/agent-mode-for-gemini-added-to-android-studio/) | Plans across files, builds and fixes errors, screenshot-to-screen, MCP tools, accept or reject each change | One agent in an IDE; the developer stays the project manager |
| [Google AI Studio, Android build](https://blog.google/innovation-and-ai/technology/developers-tools/google-ai-studio-io-2026?authuser=6) (I/O, May 2026) | Prompt to Kotlin and Compose app, in-browser emulator, ADB install, path to Play internal testing | Early release limits app types; little visible architecture, test or compliance control |
| Prompt-to-app web builders (Bolt, Lovable, v0) | Live preview loop; fast iteration on looks | Web-first; regenerate-whole-file edits break larger codebases |
| Android Studio Migration Assistant | Ports iOS, React Native or web apps to native Compose | Migration only; no product or design phase |

What carries over: MetaGPT's typed artifacts, ChatDev's paired reviewers, SWE-agent's tool design, Agent Mode's build-and-fix loop and MCP, and AI Studio's emulator-in-the-loop preview.

## Agent roster

Twenty agents, each with one job, a short tool list, and a machine-checkable "done" test. Agents marked *(critic)* never write product code; they only approve or reject.

### Command squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **1. Orchestrator** | Turns the goal into a task graph, assigns agents, enforces gates, manages budget | Goal, Project Graph → task DAG, run log | Scheduler, cost meter, gate API | All tasks closed and the release gate passed |
| **2. Memory Keeper** | Owns the Project Graph: specs, decisions (ADRs), code index, past failures | Every artifact → indexed graph, per-agent context packs | Vector + symbol index, git history | Each agent's context pack fits its window and cites sources |

### Product squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **3. Product Strategist** | Interviews the user, cuts scope to an MVP, writes stories with acceptance criteria | Idea, answers → PRD, Gherkin criteria, MVP cut line | Question flow, PRD template | User signs off the spec (gate 1) |
| **4. Research Scout** | Finds competitor patterns, the right libraries and APIs, and Play policy limits for the category | PRD → research brief, library shortlist with versions | Web search, Maven Central, Play policy docs | Every PRD feature has a feasible library or API path |

### Design squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **5. UX Flow Designer** | Maps screens, navigation and every state (empty, loading, error, offline) | PRD → nav graph, screen specs, state tables | Flow DSL, wireframe renderer | Every story maps to a screen path |
| **6. Design System Agent** | Builds the Material 3 theme, tokens, components and adaptive layouts; ingests screenshots or Figma | Brand input, screen specs → theme code, component catalog, previews | Figma MCP, image-to-layout, Compose previews | User signs off the previews (gate 2) |
| **7. Accessibility and Localization Agent** *(critic)* | Checks contrast, touch targets, TalkBack labels, font scaling, RTL; extracts strings | Screens, theme → a11y report, strings.xml per locale | Accessibility Test Framework, translation model | Zero blocking a11y findings |

### Engineering squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **8. Android Architect** | Picks modules, layers (UI, domain, data), DI, min/target SDK, and writes the Gradle setup | PRD, research brief → module graph, ADRs, version catalog, skeleton repo | Gradle, project templates, dependency checker | Skeleton builds green; module rules enforced by lint |
| **9. UI Engineer** | Implements Compose screens and navigation from the specs and theme | Screen specs, components → screen code, previews | Kotlin LSP, Compose preview renderer, edit-then-lint | Screens match design within the visual-diff threshold |
| **10. Domain and Data Engineer** | Writes ViewModels, use cases, repositories, Room schema, DataStore, WorkManager jobs, offline sync | Stories, module graph → domain and data modules, migrations | Kotlin LSP, Room schema validator | Unit tests pass; migrations verified |
| **11. Backend and Integrations Engineer** | Sets up auth, database, storage, push and third-party APIs; generates typed clients | PRD, data model → backend config, API clients, rules | Firebase or Supabase CLI, OpenAPI codegen | Integration tests pass against a staging backend |
| **12. Device Capabilities and On-device AI Engineer** | Handles camera, location, Bluetooth, NFC, sensors, notifications, permissions, and Gemini Nano or ML Kit features | Stories needing hardware → feature modules, permission rationale screens | Emulator sensor controls, permission matrix | Each permission has a just-in-time prompt and a denied-path test |

### Quality squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **13. Build Doctor** | Fixes compile, Gradle, dependency and R8 errors with the smallest change | Build logs → patches | Gradle daemon, dependency tree, error knowledge base | Clean build on CI |
| **14. Test Engineer** | Writes unit, Compose UI and screenshot tests from the acceptance criteria | Gherkin criteria, code → test suites, coverage report | JUnit, Turbine, Compose testing, Roborazzi or Paparazzi | Every criterion has a passing test |
| **15. Device QA Explorer** | Drives the real app on an emulator farm like a user would, hunts crashes and dead ends | Installed APK, nav graph → bug reports with video and repro steps | ADB, UI Automator, screen recorder, device matrix | No crash or ANR across the device matrix |
| **16. Code Reviewer** *(critic)* | Reviews every change for correctness, architecture rules and readability | Diffs, ADRs → approve or request changes | Detekt, ktlint, Android Lint, diff viewer | Approval on each pull request |
| **17. Security and Privacy Agent** *(critic)* | Scans for secrets, insecure storage, exported components, weak network config, over-broad permissions; drafts the Data safety form | Code, manifest, dependencies → findings, data-flow map | MobSF, OWASP MASVS checks, dependency CVE scan | Zero high-severity findings |
| **18. Performance Agent** | Measures startup, jank, memory and APK size; adds Baseline Profiles | Release build → benchmark report, profile files | Macrobenchmark, Perfetto, APK Analyzer | Meets the budgets set in the PRD |

### Release and growth squad

| Agent | Mission | Reads → writes | Tools | Done when |
| --- | --- | --- | --- | --- |
| **19. Release Manager** | Signs the AAB, writes the listing and screenshots, files the Data safety and content-rating forms, runs staged rollout | Release build, reports → Play submission | Play Developer API, Gradle Play Publisher, Fastlane | User approves release (gate 3); internal track live |
| **20. Post-launch Analyst** | Reads crashes, vitals and reviews and turns them into prioritized backlog items | Crashlytics, Play Vitals, reviews → new tasks for the Orchestrator | Crashlytics API, Play Console reports | Weekly backlog delivered; regressions triaged in 24 h |

## Orchestration

*Diagram (not exported from the live doc):* five phases (Product → Design → Engineering → Quality → Release) with three human gates (spec, design, release). Quality loops back to Engineering with evidence; launch data loops back to the Project Graph as new tasks. The Orchestrator and Memory Keeper assign work and own the shared Project Graph.

Quality is the only phase that can close engineering work; a failure loops back with evidence, and launch data loops back as new tasks.

- **Publish and subscribe on artifacts.** Agents watch the Project Graph and start when all their inputs exist, as in MetaGPT. No agent talks to another directly.
- **Parallel where safe.** The Architect's module graph lets UI, Data, Backend and Device engineers work on separate modules at once, each on its own branch.
- **Bounded fix loops.** A task gets at most five build-test-fix rounds. After that the Orchestrator escalates to the user with the failing evidence instead of burning budget.
- **Gates.** Three human gates by default (spec, design, release). Users can add gates or switch to full auto-approve, except for production release.
- **Every handoff is typed.** Spec, nav graph, theme, module graph, test report and release bundle each have a schema, so a malformed handoff fails fast.

## Enhancements beyond prior art

Ten additions that no single documented system combines today.

1. **Executable acceptance criteria.** The Product Strategist writes Gherkin; the Test Engineer compiles each line into a Compose UI test before the screen exists. The spec becomes the test suite, so "done" is never a matter of opinion.
2. **Design-to-device visual diff.** Each screen is rendered on the emulator and compared to the approved preview; drift above a threshold sends the task back to the UI Engineer automatically.
3. **Explorer agent on a device matrix.** Device QA runs the app on phone, foldable, tablet, small screen, dark mode, large font, RTL, slow network and low memory, recording video for every bug.
4. **Failure memory.** The Memory Keeper stores every build error and its fix. The Build Doctor checks this first, so a repeat Gradle or R8 error is fixed in one step instead of a new reasoning loop.
5. **Context packs, not full history.** Each agent gets only the slice of the Project Graph it needs, cited by artifact ID. This avoids the information overload the MetaGPT paper warns about and keeps cost flat as the app grows.
6. **Critic-maker pairs with execution veto.** Every maker agent has a critic, but a critic can only block with evidence: a failing test, a lint rule or a scan finding. This stops endless review loops seen in chat-based systems.
7. **Diff-only edits.** Agents edit with targeted patches validated by the Kotlin compiler and ktlint, never whole-file regeneration, so large codebases stay stable.
8. **Policy as a first-class input.** Play policy, target-SDK deadlines and Data safety rules are loaded at the spec stage, not discovered at submission.
9. **Three entry modes.** From an idea, from a design (screenshot or Figma), or from an existing app (iOS, React Native, web or legacy Android Views) using a migration path similar to Android Studio's Migration Assistant.
10. **Closed loop after launch.** The Post-launch Analyst feeds crashes, vitals and reviews back as tasks, so the same agent team maintains the app it shipped.

## Tooling and infrastructure

Agents reach every tool through MCP servers with small, documented commands, so any model or IDE (including Android Studio's own agent) can plug in.

| Layer | Components | Used by |
| --- | --- | --- |
| Build sandbox | Container per project with JDK, Android SDK, warm Gradle daemon and build cache | Architect, all engineers, Build Doctor |
| Code tools | Kotlin LSP, edit-then-lint command, ktlint, Detekt, Android Lint, symbol search | Engineers, Code Reviewer |
| Device farm | Headless emulators (phone, foldable, tablet, Wear optional), ADB, UI Automator, screen recording; optional real-device cloud | Test Engineer, Device QA, Performance |
| Preview service | Compose preview renderer and screenshot tests streamed to the user's browser | Design System, UI Engineer, user |
| Project Graph store | Git repo plus a typed artifact store (specs, ADRs, reports) and a vector and symbol index | Memory Keeper, everyone |
| Backend adapters | Firebase, Supabase or custom REST/GraphQL, each behind a codegen step | Backend Engineer |
| Security tools | MobSF, secret scanner, dependency CVE feed, network-security-config checker | Security and Privacy |
| Release tools | Gradle Play Publisher or Fastlane, Play Developer API, signing key vault | Release Manager |
| Model router | Strong reasoning model for Orchestrator, Architect and critics; faster model for bulk code and tests | Orchestrator |

## Security and trust model

Agents that run code, install packages and publish to a store need hard limits, not just instructions.

- **Sandbox every build.** No agent runs Gradle or tests on the user's machine. Network access is limited to Maven Central, Google Maven and approved registries.
- **Secrets never reach a model.** Signing keys, API keys and Play credentials live in a vault. The Release Manager calls a signing service; it never sees the key.
- **Dependency allowlist.** New libraries need the Research Scout's version pin and a clean CVE scan. This blocks typosquatted or abandoned packages.
- **Untrusted inputs stay data.** Text inside web pages, library READMEs, Figma files or user-uploaded apps is treated as content, never as instructions to agents (prompt-injection defense).
- **Irreversible actions need a human.** Production rollout, deleting backend data, and changing permissions on a live app always wait for gate 3, even with auto-approve on.
- **Full audit trail.** Every tool call, diff and approval is logged against the task that caused it.

## Evaluation and roadmap

Build the builder in four phases, each proven on a fixed benchmark of about 50 app specs (to-do, habit tracker, camera notes, BLE device companion, offline field form, and so on) before the next starts.

**Metrics to track per run**

| Metric | What it measures |
| --- | --- |
| First-green-build rate | Share of runs whose skeleton builds with no human edits |
| Acceptance pass rate | Share of Gherkin criteria with a passing test |
| Crash-free sessions on the device matrix | Stability before release |
| Visual-diff score | How closely screens match approved design |
| Human interventions per app | Edits or nudges beyond the three gates |
| Cost and wall-clock per app | Model tokens, compute minutes, elapsed time |
| Play pre-launch report findings | Policy, a11y and security issues Google flags |

**Phases**

1. **Core loop (MVP).** Orchestrator, Memory Keeper, Product Strategist, Architect, UI Engineer, Data Engineer, Build Doctor and Test Engineer. Output: a single-module app that builds and passes its tests.
2. **Design and quality.** Add UX Flow, Design System, Accessibility, Code Reviewer and Device QA with the visual-diff loop and device matrix.
3. **Real-world apps.** Add Backend, Device Capabilities, Security and Performance. Support multi-module builds, auth, sync and hardware features.
4. **Ship and sustain.** Add Release Manager, Post-launch Analyst and the design and migration entry modes.

## Sources

- [MetaGPT on GitHub](https://github.com/geekan/MetaGPT) and [paper summary of roles and structured communication](https://artificialanalysis.ai/microevals/3-metagpt-a-meta-programming-framework-metagpt-is-a-meta-p-1788604268435)
- [ChatDev overview, Pragmatic Coders](https://www.pragmaticcoders.com/resources/ai-developer-tools)
- [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering (arXiv 2405.15793)](https://arxiv.org/abs/2405.15793v2)
- [Agent Mode for Gemini added to Android Studio, SD Times](https://sdtimes.com/mobile/agent-mode-for-gemini-added-to-android-studio/)
- [Gemini 3 in Android Studio, Android Developers Blog](https://developer.android.com/blog/posts/gemini-3-is-now-available-for-ai-assistance-in-android-studio?authuser=2)
- [Bring any idea to life: Google AI Studio at I/O 2026, Google](https://blog.google/innovation-and-ai/technology/developers-tools/google-ai-studio-io-2026?authuser=6)
- [AI Studio builds Android apps, Android Studio adds iOS porting, 9to5Google](https://9to5google.com/?p=714991)
