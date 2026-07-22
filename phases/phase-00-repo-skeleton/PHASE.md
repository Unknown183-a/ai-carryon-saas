<!-- Self-contained phase brief. Companion docs: ../../BUILD_GUIDE.md (full build order) and ../../docs/architecture/AI-CarryON-Architecture.html (the why). -->

## Phase 0 — Repo & Skeleton
*(SAD reference: Chapter 13 — Folder Structure)*

**Goal:** an empty but correctly-shaped repo exists, so no later phase needs to restructure folders.

**Depends on:** nothing.

**Tasks:**
- [ ] Run the skeleton command below
- [ ] Commit with message `chore: initial folder skeleton`
- [ ] Add `.env` to `.gitignore`, commit `.env.example` instead
- [ ] Add a root `README.md` that just links to this file and the SAD

```bash
mkdir -p ai-carryon/{frontend,backend/{app/{api/{routers,middleware},core,services,models,database,workers},ai/{agents,langgraph,memory,rag,prompts,models,tools},platform/{channels,factory,workspace,scheduler,monitoring,security},integrations/{firebase,youtube,gemini,openai,groq},configs},deployment,tests,docs/{architecture,api,decisions,deployment,diagrams},docker,.github/workflows}
cd ai-carryon && git init && git add . && git commit -m "chore: initial folder skeleton"
```

**Definition of Done:** `tree -L 3` shows every folder from Chapter 13's tree; repo is pushed to GitHub.

**Handoff Notes:**
> _(empty — fill in if you stop here)_

---
