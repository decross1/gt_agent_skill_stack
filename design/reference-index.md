# Design & Visualization Reference Index (`design/reference-index.md`)

Maps user questions and data shapes to local reference files, upstream open-source repositories, and foundational research papers. Load only the specific reference file needed for the active task.

---

## 1. Question-to-Reference Router

| User Question / Data Shape | Local Reference File | Canonical Representations | Primary Upstream Sources & Papers |
|---|---|---|---|
| **How is the research program progressing? Where do hypotheses die or promote?** | [`design/references/evidence-state.md`](./references/evidence-state.md) | Ladder funnel (`L0`→`L5` with explicit `0`), Vote matrix (`finding × reviewer`), Kill-reason Pareto, Promotion audit trail, Liveness strip | Self-authored lab standard; LineUp (Gratzl et al., 2013); Trrack (Cutler et al., 2020) |
| **Which agent needs attention? Where did a run or trace diverge?** | [`design/references/runtime.md`](./references/runtime.md) | Swimlane/status timeline, Agent-Prism 4-view trace inspector (tree, cost/latency timeline, span detail, sequence), AGDebugger flat-band loop detector, per-step repo diff | AgentLens (Lu et al., 2024); Evil Martians `agent-prism`; AGDebugger (Epperson et al., CHI 2025); AgentStepper (2026); Langfuse; Arize Phoenix |
| **What does an agent believe, when was it valid, and what superseded it? How is context budget allocated?** | [`design/references/memory.md`](./references/memory.md) | Letta ADE stacked context-window budget bar; Zep/Graphiti 4-timestamp bitemporal timeline (`valid_from`, `valid_to`, `created_at`, `expired_at`); MAGMA 4-layer causal/temporal linearization | Zep / Graphiti (Rasmussen et al., 2025, `arXiv:2501.13956`); MAGMA (Jiang et al., ACL 2026, `arXiv:2601.03236`); Letta ADE; EverMemOS (`arXiv:2601.02163`) |
| **What is connected to this note, decision (`D-NNN`), or hypothesis? How should spatial canvases behave?** | [`design/references/graphs.md`](./references/graphs.md) | Focused 2D spatial neighborhood canvas (inline SVG / HTML5 Canvas for `<2k` nodes), Foundation Capital decision trace table/graph, Control Panel vs. Spatial Workspace topology | React Flow / `xyflow`; Obsidian JSON Canvas; Sigma.js v3 / Graphology; `cosmos.gl`; UW Mosaic; Foundation Capital Context Graphs (2025) |
| **Which experiment improved the outcome? Which parameters matter across a sweep or QD archive?** | [`design/references/experiments.md`](./references/experiments.md) | Sakana AI-Scientist-v2 Hypothesis Tree (`H0/H1`, controlled diff, seed, metric), `pyribs` 2D QD archive niche heatmap, Aim grouped run comparison, HiPlot parallel coordinates, Trrack provenance | Sakana `AI-Scientist-v2` (`arXiv:2504.08066`); `pyribs` (`icaros-usc/pyribs`); Aim (`aimhubio/aim`); HiPlot; Trrack (`Trrack/trrackjs`) |
| **Do strategies form a non-transitive cycle? Why is a candidate ranked higher?** | [`design/references/game-theory.md`](./references/game-theory.md) | Pairwise payoff matrix + directed response graph, Alpha-Rank Markov stationary mass & fixation network, Spinning Top (skill vs. cycle width), LineUp stacked attribute bars, transfer flow matrix | Omidshafiei et al. 2019 (`Alpha-Rank`) & 2020 (`arXiv:2005.01642`); Czarnecki et al. 2020 (`Spinning Tops`, `arXiv:2004.09468`); OpenSpiel; LineUp; `lf-game-theory` |
| **What happened in a spatial simulation over time, or how do mathematical constraints relate?** | [`design/references/spatial-and-diagrams.md`](./references/spatial-and-diagrams.md) | Rerun synchronized time-scrubber + multimodal viewport; Penrose declarative constraint diagram + co-located mathematical specification | Rerun (`rerun-io/rerun`); Penrose (Ye et al., SIGGRAPH 2020, `penrose/penrose`) |
| **How do we enforce visual hierarchy, zero-dep portability, Tufte density, and deterministic QA?** | [`design/references/house-constraints.md`](./references/house-constraints.md) | Shared CSS token compliance, 4:3 figure spec, 390px/1280px responsive grid, anti-slop rules, `design/scripts/qa_gate.py` | Munzner Nested Model (2009); Interface Design (`Dammyjay93/interface-design`); Impeccable (`pbakaus/impeccable`); Vercel `agent-skills`; Edward Tufte |

---

## 2. Foundational Papers & Architectural Lessons

1. **Tamara Munzner (2009), *A Nested Model for Visualization Design and Validation***:
   - Separates (1) Domain situation, (2) Task and data abstraction, (3) Visual encoding and interaction idiom, and (4) Algorithm/implementation.
   - **Rule:** Never pick a visual encoding (Level 3) before writing down the user's question and data/task abstraction (Levels 1–2) in a Screen Brief (`lab-ui-plan`).
2. **Lu et al. (2024), *AgentLens: Visual Analysis for Agent Behaviors in LLM-based Autonomous Systems*** & **Epperson et al. (CHI 2025), *AGDebugger***:
   - Combine high-level temporal summary strips with progressive drill-down into span details and message resets. Repetitive bands in the overview expose stuck agent loops immediately.
3. **Rasmussen et al. (2025), *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*** & **Jiang et al. (ACL 2026), *MAGMA***:
   - Memory is bitemporal and multi-layered (`Semantic`, `Temporal`, `Causal`, `Entity`). Never flatten memory into an undated node-link hairball; expose validity windows (`valid_from` → `valid_to`), supersession links (`expired_at`), and topologically sorted causal chains (`E_causal`).
4. **Omidshafiei et al. (2019, 2020), *Alpha-Rank* & *Navigating the Landscape of Multiplayer Games*** + **Czarnecki et al. (NeurIPS 2020), *Real World Games Look Like Spinning Tops***:
   - Scalar Elo/win-rate rankings hide non-transitive cycles (`Rock-Paper-Scissors` / meta-game loops). Pair summary rankings with a pairwise payoff matrix, directed response graph (node intensity = stationary mass, edge = fixation preference), and transitive-vs-cyclical width views.
5. **MindSkillEvolve (Noah's Ark Lab, 2026, `arXiv:2608.12428`)** & **Agent Trace Specification (`superhq-dev/agent-trace`)**:
   - Close the self-improvement loop after UI/UX sessions by recording mutations as a 5-tuple (`what`, `when`, `who`, `why`, `where`) and distilling human corrections into deterministic `qa_gate.py` checks and ReHarness backward qualifications (`verify_reharness_qualifications.py`).
