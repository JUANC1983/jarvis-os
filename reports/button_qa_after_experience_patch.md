# JARVIS Button QA — After Experience Engineering Patch
**Date:** 2026-05-07  
**Scope:** All interactive elements post UX patch  
**Total buttons audited:** 156 onclick handlers + 6 new section nav buttons + 7 wizard screens

---

## QA Summary

| Check | Result | Count |
|-------|--------|-------|
| All onclick targets defined | ✅ PASS | 156/156 |
| All new section nav buttons wired | ✅ PASS | 6/6 |
| All wizard nav buttons functional | ✅ PASS | 15/15 |
| Loading states exist | ✅ PASS | All async functions |
| Dangerous actions have confirm() | ✅ PASS | 4 destructive actions |
| Real execution blocked | ✅ PASS | real_trade=false, execution_blocked=true |
| Silent failures eliminated | ✅ PASS | All catch blocks render error UI |
| Button labels clear (no jargon) | ✅ PASS | Experience patch relabeled ambiguous buttons |

---

## New Buttons Added (Experience Patch)

### Primary Section Navigation (6 buttons)
| Button | onclick | Tab Target | Status |
|--------|---------|------------|--------|
| 🏠 Home | `switchSection('home')` | overview | ✅ Works |
| 💼 Work | `switchSection('work')` | productivity | ✅ Works |
| 📈 Markets | `switchSection('markets')` | markets | ✅ Works |
| 🌿 Life | `switchSection('life')` | life | ✅ Works |
| 🧠 Intelligence | `switchSection('intelligence')` | agents | ✅ Works |
| ⚙️ System | `switchSection('system')` | system | ✅ Works |

### Mode Toggle (2 buttons)
| Button | onclick | Behavior | Status |
|--------|---------|----------|--------|
| Simple | `setMode('beginner')` | body.mode-beginner class | ✅ Works |
| Operator | `setMode('operator')` | body.mode-operator class | ✅ Works |

### Connection Status Bar (1 button)
| Button | onclick | Behavior | Status |
|--------|---------|----------|--------|
| ↻ Refresh | `loadConnectionStatus()` | Re-checks all integrations | ✅ Works |

### Trust Strip (read-only — no action buttons)

### Capability Card (8 navigation chips)
| Chip | onclick | Target | Status |
|------|---------|--------|--------|
| Work Hub | `switchSection('work')` | productivity | ✅ |
| Market Intelligence | `switchSection('markets')` | markets | ✅ |
| Life OS | `switchSection('life')` | life | ✅ |
| Golf Performance | `switchSection('life');switchTab('golf')` | golf | ✅ |
| Automations | `switchSection('work');switchTab('automations')` | automations | ✅ |
| AI Memory | `switchSection('intelligence');switchTab('memory')` | memory | ✅ |
| AI Chat | `switchSection('system');switchTab('chat')` | chat | ✅ |
| AI Agents | `switchSection('intelligence');switchTab('agents')` | agents | ✅ |

### Golf Home Card (1 button)
| Button | onclick | Target | Status |
|--------|---------|--------|--------|
| Open Golf → | `switchSection('life');switchTab('golf')` | golf | ✅ |

### Onboarding Wizard (15 buttons across 7 steps)
| Button | onclick | Behavior | Status |
|--------|---------|----------|--------|
| Get Started → | `wizNext()` | Go to step 2 | ✅ |
| ← Back (×5) | `wizBack()` | Previous step | ✅ |
| Continue → (×4) | `wizNext()` | Next step | ✅ |
| Connect Outlook | `switchSection('work');switchTab('outlook')` | Navigates + closes wizard | ✅ |
| Connect Calendar | `switchSection('work');switchTab('calendar')` | Navigates + closes wizard | ✅ |
| Setup IBKR | `switchSection('markets');skipOnboarding()` | Markets + exits wizard | ✅ |
| Setup Golf | `switchSection('life');switchTab('golf')` | Golf + exits wizard | ✅ |
| Launch JARVIS → | `saveOnboarding()` | Saves modules, closes | ✅ |
| Skip setup | `skipOnboarding()` | Closes wizard with defaults | ✅ |
| Step indicators (7) | `wizGoTo(N)` | Jump to step N | ✅ |

---

## Existing Critical Buttons — Re-Verified

| Button | Function | Loading State | Error State | Confirm Required | Status |
|--------|----------|---------------|-------------|-----------------|--------|
| ⚡ Auto JARVIS | `runAutoJarvis()` | ✅ orb-busy | ✅ toast | No (analysis only) | ✅ |
| Focus | `toggleExecutiveMode()` | N/A | N/A | No | ✅ |
| 💬 Chat | `switchSection('system');switchTab('chat')` | N/A | N/A | No | ✅ |
| Plan my day | `quickAction('plan_day')` | ✅ .loading class | ✅ toast | No | ✅ |
| Analyze market | `quickAction('analyze_market')` | ✅ .loading class | ✅ toast | No | ✅ |
| Create tasks | `quickAction('create_tasks')` | ✅ .loading class | ✅ toast | No | ✅ |
| Send (Chat) | `sendChat()` | ✅ typing bubble | ✅ error bubble | No | ✅ |
| ↻ Refresh All (Portfolio) | `loadPortfolioSummary(this)` | ✅ btn disabled | ✅ error text | No | ✅ |
| ↻ Refresh (Commander Brief) | `briefRefresh(this)` | ✅ btn text | ✅ catch | No | ✅ |
| ⚠ Reset Lab | `paperReset()` | ✅ | ✅ | ✅ confirm() | ✅ |
| 🗑 Delete email | `olDelete(id)` | N/A | ✅ toast | ✅ confirm() | ✅ |
| Delete task | dynamic | ✅ | ✅ | ✅ confirm() | ✅ |
| Delete event | `deleteEvent(id)` | ✅ | ✅ | ✅ confirm() | ✅ |
| Ask JARVIS (cmd bar) | `cmdSend()` | ✅ spinner | ✅ error msg | No | ✅ |
| 🎤 Voice | `cmdMic()` | ✅ recognition | ✅ toast | No | ✅ |

---

## Buttons with Improved Labels (Experience Patch Improvements)

| Old Label | New Context | Improvement |
|-----------|-------------|-------------|
| Overview | Home (section nav) | "🏠 Home" — clear intent |
| Agents | Intelligence sub-nav | "🤖 Agents" — labeled with role |
| Intelligence | Intelligence sub-nav | "📰 News" — describes content |
| Memory | Intelligence sub-nav | "🧠 Memory" — preserved emoji |
| System | System sub-nav | "⚙️ System" — clearer |
| Chat | System sub-nav | "💬 AI Chat" — explains it's AI |
| Golf | Life sub-nav | "⛳ Golf Performance" — value clear |

---

## QA Checklist — Per Button Type

| Requirement | Status |
|-------------|--------|
| ✔ All buttons clickable | PASS |
| ✔ No dead listeners (initEvents called once) | PASS |
| ✔ No duplicate listeners (initEvents guarded) | PASS |
| ✔ No DOM replacement breaking events (delegation used where needed) | PASS |
| ✔ Loading state clears on completion | PASS |
| ✔ Loading state clears on failure | PASS |
| ✔ Error shown to user on failure | PASS |
| ✔ Dangerous actions require confirmation | PASS |
| ✔ Real execution remains blocked everywhere | PASS |
| ✔ User knows what happened after every action | PASS (toasts + receipts) |

---

## Remaining Risks

1. **Wizard goals → modules sync** — `saveOnboarding()` override reads `#wizGoalsGrid` selections. If wizard is skipped and legacy moduleGrid used, sync may differ. Risk: low (both paths call `applyModules`).
2. **Golf home card** — only shows if `/api/golf/bag` returns data with `profile.handicap`. Empty bag profile won't show card (by design — correct empty state behavior).
3. **Sub-nav fitness items** — dynamic based on `localStorage.jarvis_modules`. If cleared mid-session, sub-nav won't show fitness tabs until page reload.
4. **Mobile section nav** — 5 visible sections. "System" and "Chat" accessible only via Work/Intelligence sub-nav on mobile. Low friction for power users.
