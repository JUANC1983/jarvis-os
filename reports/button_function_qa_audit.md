# JARVIS Button & Function QA Audit
**Audit Date:** 2026-05-07  
**Scope:** All visible buttons, interactive elements, and action endpoints  
**Method:** Static HTML analysis + API endpoint mapping + behavioral simulation

---

## QA Risk Levels
- **CRITICAL** — broken, dangerous, or misleading behavior
- **HIGH** — confusing, inconsistent, or unreliable
- **MEDIUM** — minor friction, unclear but functional
- **LOW** — cosmetic, minor wording issues

---

## 1. Command Bar

| Button | Location | Expected Behavior | Endpoint Called | Failure Mode | User Feedback Quality | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|-----------------|--------------|----------------------|----------|-------|---------|
| **Ask** | Top command bar | Send message to JARVIS chat | POST /chat | Spinner but no persistent result panel | Poor — result appears in overlay that auto-dismisses | Partially (why "Ask" not "Send"?) | Yes | MEDIUM |
| **🎤 Voice Input** | Top command bar | Open mic, transcribe speech | Browser webkitSpeechRecognition | Falls silently if no mic permission | No error shown if permission denied | No — icon too small | Yes | HIGH |
| **ES/EN Toggle** | Top command bar | Switch voice language | Client-side only | No feedback if API doesn't support lang | None | No — 18px, easily missed | Yes | MEDIUM |
| **✕ Dismiss** | Command result overlay | Close result overlay | None | Result permanently lost | None | Yes | Yes | LOW |

**Issues:**
- "Ask" and "Send" are used for the same action in different UI locations — inconsistent
- Command result appears in a floating overlay that auto-dismisses — users lose results
- No persistent chat log visible after command bar submit
- Voice input uses `webkitSpeechRecognition` — Chrome-only, fails silently on Firefox/Safari

---

## 2. Overview Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback Quality | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|-----------------|----------|-------|---------|
| **⚡ Auto JARVIS** | Hero section | Run full market scan | POST /jarvis/auto | Error returned as JSON, no user message | Poor — no loading state | Partially | Yes | HIGH |
| **Focus** (Executive Mode) | Hero section | Toggle executive/focus view | Client-side | No visible change unless in full layout | None | No — label says "Focus" not what it does | Yes | MEDIUM |
| **💬 Chat** | Hero section | Navigate to Chat tab | switchTab('chat') | None | None | Yes | Yes | LOW |
| **🔔 Notifications** | Hero section | Open notifications dropdown | GET /api/notifications | Bell shows badge but dropdown is tiny | Poor if many notifications | Yes | Yes | MEDIUM |
| **Mark all read** | Notifications dropdown | Mark all unread as read | PUT /api/notifications/read-all | Silent failure if API fails | None | Yes | Yes | LOW |
| **↻ Refresh** (Priority Center) | Overview top | Reload unified priorities | GET /api/commander/brief + others | Loading state stuck with no timeout | Poor — "Loading priorities…" forever | Yes | Yes | MEDIUM |
| **📅 Plan my day** | Action bar | Trigger day planning | POST /api/quick-action | Returns text reply only, no tasks created | Confusing — user expects task list | Partially | Yes | HIGH |
| **📈 Analyze market** | Action bar | Run market analysis | POST /api/quick-action | Returns text, no chart or visual | Medium — text result shown | Partially | Yes | MEDIUM |
| **✅ Create tasks** | Action bar | Open task creation flow | POST /api/quick-action | Returns text suggestions, no direct creation | Poor — user expects task input form | No | Yes | HIGH |
| **💪 Start workout** | Action bar | Start workout tracking | POST /api/quick-action | Returns text only, no tracking started | Poor | No | Yes | MEDIUM |
| **↻** (JARVIS Insights) | WOW section | Refresh insights | GET /api/wow/insights | No error if service unavailable | None | Yes | Yes | LOW |
| **↻** (Commander Brief) | Commander Brief | Reload daily brief | GET /api/commander/brief | Skeleton loader stays if API fails | Poor | Yes | Yes | MEDIUM |
| **🎙 Voice** | Commander Brief | Sends text chat command | POST /chat with "dame mi briefing" | Not actual voice — sends text command | Misleading — icon implies voice | No | Yes | HIGH |
| **↻** (Command History) | Command History | Load recent commands | GET /api/command/history | Empty list if no history | OK | Yes | Yes | LOW |
| **⚙ Modules** | Overview personality row | Open module settings dialog | Client-side dialog | Dialog appears but has no save animation | Medium | No | Yes | MEDIUM |
| **personality-tone-label** | Overview | Cycle personality (prof/exec/casual) | POST /api/personality/respond | No confirmation of change | Poor | No — needs tooltip | Yes | MEDIUM |

**Critical Issues:**
- "Plan my day" quick action does NOT create tasks — it only sends a chat message. A user pressing this expects tasks to be created.
- "Create tasks" quick action has the same problem.
- "🎙 Voice" in Commander Brief sends text, not voice — icon is misleading.
- "Auto JARVIS" runs a market analysis silently — no loading state, result not prominently shown.

---

## 3. Markets Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **↻ Refresh All** | Markets header | Reload all portfolio panels | GET /api/portfolio/cockpit | Portfolio zeros if IBKR offline | Poor — "0" shown as value | Yes | Yes | HIGH |
| **Reconnect** | Connection error state | Retry IBKR connection | GET /api/portfolio/cockpit | Shown only in error — unclear if retry worked | Poor | Yes | Yes | MEDIUM |
| **Cockpit** sub-tab | Markets nav | Show real portfolio panel | Client switch | None | None | Yes | Yes | LOW |
| **Paper Lab** sub-tab | Markets nav | Show paper trading panel | Client switch | None | None | Partially | Yes | LOW |
| **AI Learning** sub-tab | Markets nav | Show learning panel | Client switch | None | None | No — "Learning" of what? | Yes | MEDIUM |
| **Analysis** sub-tab | Markets nav | Show analysis tools | Client switch | None | None | Partially | Yes | LOW |
| **↓ Import Real** | Paper Lab panel | Import real IBKR portfolio to paper | POST /api/paper/import-from-real | Imports silently if IBKR offline — gets zeros | No confirmation dialog | No — dangerous | Partially | CRITICAL |
| **↻ Refresh Lab** | Paper Lab panel | Reload paper analytics | GET /api/paper/analytics | Empty if no paper trades | OK | Yes | Yes | LOW |
| **Compare Now** | Paper Lab compare card | Compare paper vs real performance | GET /api/paper/compare-real | Shows "no data" silently | Medium | Yes | Yes | MEDIUM |
| **Simulate Trade** | Paper Lab trade form | Submit simulated trade | POST /api/paper/simulate-trade | Validation errors not shown prominently | Medium | Partially | Yes | MEDIUM |
| **↻ Status** | Paper Lab | Reload paper status | GET /api/paper/status | None | OK | Yes | Yes | LOW |
| **Compare vs Real** | Paper Lab | Same as Compare Now — duplicate | GET /api/paper/compare-real | Duplicate button of "Compare Now" | Confusing | No | Yes | HIGH |
| **⚠ Reset Lab** | Paper Lab | Delete all paper trade history | POST /api/paper/reset | One-click reset — minimal confirmation | CRITICAL — data loss | Partially | **No** | CRITICAL |
| **↻ Refresh Learning** | AI Learning | Reload AI learning panel | GET /api/trader/learning | Long load with no progress indicator | Medium | Yes | Yes | MEDIUM |
| **+ Record** | AI Learning | Record trade outcome for AI | POST /api/trader/learning/record-outcome | Form appears but purpose unclear | Poor — what are you recording? | No | Yes | HIGH |
| **Analyze** (symbol input) | Analysis panel | Analyze stock/ticker | POST /api/trader/analyze | Empty result if symbol unknown | Medium | Yes | Yes | MEDIUM |
| **↻** (Recommendations) | Analysis panel | Reload recommendations | GET /api/markets/recommended | No change if market closed | OK | Yes | Yes | LOW |
| **↻** (Market News) | Analysis panel | Reload news feed | GET /api/markets/news | None | OK | Yes | Yes | LOW |
| **Full Feed →** | Analysis panel | Go to Intelligence tab | switchTab('intelligence') | None | None | Yes | Yes | LOW |
| **Run Audit** | Trader Audit card | Run trader performance audit | GET /api/trader/audit | Audit shown as JSON dump | Poor | No — "audit" is technical | Yes | HIGH |
| **↻ Refresh** (Analysis) | Analysis panel | Reload cockpit | GET /api/portfolio/cockpit | Same as "Refresh All" — duplicate | Confusing | No | Yes | MEDIUM |

**Critical Issues:**
- **"⚠ Reset Lab"** is a one-click destructive action with NO confirmation modal. User data lost permanently.
- **"↓ Import Real"** has no warning that it will overwrite paper portfolio with real holdings — could confuse paper/real mental model.
- **"Compare Now" and "Compare vs Real"** are two buttons in two locations calling the same endpoint — confusing duplication.
- **"+ Record"** in AI Learning has no explanation. Users won't know what they're recording or why.

---

## 4. Productivity Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **Add** (Task) | Tasks section | Create new task | POST /dashboard/tasks | Empty string allowed | OK | Yes | Yes | MEDIUM |
| **Toggle** (Task) | Each task | Mark complete/incomplete | POST /dashboard/tasks/{id}/toggle | Silent fail | None | Yes | Yes | LOW |
| **Delete** (Task) | Each task | Delete task | DELETE /dashboard/tasks/{id} | No confirmation | Data loss | Partially | No | HIGH |
| **📅 Schedule** | Meetings section | Open meeting scheduler | Client-side modal | Modal doesn't validate required fields | Medium | Partially | Yes | MEDIUM |
| **Add** (Meeting) | Meetings section | Create new meeting | POST /dashboard/meetings | Empty title allowed | OK | Yes | Yes | LOW |
| **Delete** (Meeting) | Each meeting | Delete meeting | DELETE /api/meetings/{id} | No confirmation | None | Partially | No | HIGH |
| **Upload Zone** | Productivity | Upload file | POST /dashboard/upload | No file type validation shown | Medium | Yes | Yes | MEDIUM |
| **Delete** (Upload) | Asset grid | Delete uploaded file | DELETE /api/uploads/{filename} | No confirmation | None | No | No | HIGH |

---

## 5. Golf Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **📷 Start Camera** | Swing Vision | Start camera stream | Browser Camera API | Fails if no camera permission | No error message | Yes | Yes | HIGH |
| **⏺ Record Swing** | Swing Vision | Start recording | MediaRecorder API | Disabled until camera starts | OK — button disabled | Yes | Yes | LOW |
| **🔄 Switch Camera** | Swing Vision | Switch front/rear camera | Browser MediaDevices | Fails on desktop (no rear camera) | No error | Yes | Yes | MEDIUM |
| **Get Club Rec.** | Caddie | Get club recommendation | POST /api/golf/caddy | Empty result if no conditions set | Medium | Yes | Yes | LOW |
| **🌤 Use Live Weather** | Caddie | Fill weather from API | GET /api/context/weather | Shown only when weather available | OK | Yes | Yes | LOW |
| **All / Filters** | Course Library | Filter courses | Client-side filter | None | OK | Yes | Yes | LOW |
| **+ Club** | Golf Bag | Add club to bag | POST /api/golf/bag | No validation | OK | Yes | Yes | LOW |
| **↻** (Golf Bag) | Golf Bag | Reload bag | GET /api/golf/bag | None | OK | Yes | Yes | LOW |
| **+ Log Round** | Golf Profile | Log new round | POST /api/golf/profile/round | No form validation visible | Medium | Yes | Yes | MEDIUM |

---

## 6. Chat Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **Send** | Chat input | Send chat message | POST /chat | Empty message allowed | OK — response rendered | Yes | Yes | LOW |
| **🎙 Voice** | Chat | Start voice input | Browser STT API | Fails on non-Chrome | No error message | Yes | Yes | HIGH |
| **■ Stop** | Chat | Stop voice recording | Client-side | Works | OK | Yes | Yes | LOW |
| **🔊 Speak** | Voice bar | Read last reply aloud | POST /api/voice/speak | Falls back if ElevenLabs unavailable | None | Yes | Yes | LOW |
| **⏹ Stop** | Voice bar | Stop audio playback | Client-side | Works | OK | Yes | Yes | LOW |
| **🔁 Auto** | Voice bar | Toggle auto-speak | Client-side | No persistence on reload | OK | Partially | Yes | MEDIUM |
| **🎙 Mic** | Voice bar | Start voice input | Browser STT API | Same as Voice button above | Duplicate function | No — duplicate | Yes | MEDIUM |
| **👂 Wake** | Voice bar | Enable wake word "Hey JARVIS" | Client-side | No visual indicator when active | None | No | Yes | HIGH |
| **⚙ Settings** | Voice bar | Open voice settings panel | Client-side expand | Settings require reload to apply | Medium | Partially | Yes | MEDIUM |
| **📋 Log** | Voice bar | Show voice command history | GET /api/voice/history | Empty if no history | OK | Yes | Yes | LOW |
| **Save** (Voice settings) | Voice settings panel | Save voice config | PUT /api/voice/settings | No success confirmation | Poor | Yes | Yes | MEDIUM |
| **Quick suggestions** | Chat tab | Pre-fill suggestion text | cmdSend() pre-fill | May trigger incorrect routing | OK | Yes | Yes | LOW |

**Issues:**
- "🎙 Voice" and "🎙 Mic" are duplicated — both do the same thing in slightly different locations
- Wake word has no visual indicator showing it's actively listening
- Voice settings save shows no confirmation — user doesn't know if settings persisted

---

## 7. Calendar Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **+ New Event** | Calendar header | Open event creation modal | POST /api/calendar/events | Modal lacks time zone selector | Medium | Yes | Yes | MEDIUM |
| **Today/Week/Month/All** | Calendar filters | Filter event view | Client-side filter | None | OK | Yes | Yes | LOW |
| **Delete Event** | Each event | Delete calendar event | DELETE /api/calendar/events/{id} | No confirmation dialog | Data loss | Partially | No | HIGH |
| **Edit Event** | Each event | Edit calendar event | PUT /api/calendar/events/{id} | If modal disappears, changes lost | Medium | Yes | Yes | MEDIUM |

---

## 8. Life Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **🎤 Voice** | Life NLP input | Voice-to-life-item | Browser STT | Same cross-browser issue | None | Yes | Yes | HIGH |
| **+ Add** | Life NLP input | Parse NL input → life item | POST /api/life/task etc. | Wrong category if NLP fails | Poor | Yes | Yes | MEDIUM |
| **✓ Clear Checked** | Shopping list | Delete completed shopping items | POST /api/life/shopping/clear-checked | No confirmation | Data loss | Partially | Partially | MEDIUM |
| **✓** (item done) | Each life item | Mark item complete | POST /api/life/reminder/{id}/done | None | OK | Yes | Yes | LOW |
| **✕** (item delete) | Each life item | Delete item | DELETE /api/life/reminder/{id} | No confirmation | None | Yes | No | HIGH |

---

## 9. Outlook Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **🔗 Connect Outlook** | Outlook header | Start Microsoft OAuth | GET /auth/microsoft/login | Redirect to Microsoft login | OK | Yes | Yes | LOW |
| **↻ Refresh** | Outlook header | Reload inbox | GET /api/outlook/inbox | Error if token expired | Medium — shows error card | Yes | Yes | MEDIUM |
| **🔔 Subscribe** | Outlook header | Create Graph webhook subscription | POST /api/outlook/subscribe | Fails silently if already subscribed | Poor | No — "Subscribe" to what? | Yes | HIGH |
| **Filter buttons** | Outlook inbox | Filter emails by status | Client-side filter | None | OK | Partially | Yes | MEDIUM |
| **Generate Reply** | Each email | AI generate reply draft | POST /api/outlook/email/{id}/generate-reply | Empty reply if LLM fails | Medium | Yes | Yes | MEDIUM |
| **Send Reply** | Each email | Send approved reply | POST /api/outlook/send-reply | No retry on failure | Poor | Yes | Yes | MEDIUM |
| **Delete** | Each email | Delete email | POST /api/outlook/delete/{id} | No confirmation | Irreversible | No | No | CRITICAL |
| **Ignore** | Each email | Mark as ignored | POST /api/outlook/ignore/{id} | Reversible? Unclear | None | Partially | Partially | MEDIUM |
| **Mark Read** | Each email | Mark email as read | POST /api/outlook/mark-read/{id} | None | None | Yes | Yes | LOW |
| **Create Task** | Each email | Create task from email | POST /api/outlook/email/{id}/create-task | No form shown — auto-creates | Poor — auto-create | No | Partially | HIGH |
| **Create Event** | Each email | Create calendar event from email | POST /api/outlook/email/{id}/create-event | No form shown — auto-creates | Poor — auto-create | No | Partially | HIGH |

**Critical Issues:**
- **Email Delete** has NO confirmation — irreversible action with one click
- "Subscribe" label is ambiguous — what are you subscribing to?
- Auto-create task/event from email doesn't show a form — no user review before action

---

## 10. Memory Tab Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **↻ Refresh** | Memory header | Reload memory graph | GET /api/graph/stats | None | OK | Yes | Yes | LOW |
| **⚡ Backfill from Data** | Memory | Backfill graph from history | POST /api/graph/backfill | Long-running, no progress | Poor — no spinner | No — "Backfill"? | Yes | HIGH |
| **Search** | Memory | Search memory nodes | GET /api/graph/search | Empty result | OK | Yes | Yes | LOW |
| **+ Add Node** | Memory | Add manual memory node | POST /api/graph/nodes | No validation shown | Medium | No — what is a "node"? | Yes | MEDIUM |
| **Cancel** | Add node form | Cancel node creation | Client-side | None | OK | Yes | Yes | LOW |

---

## 11. Onboarding Buttons

| Button | Location | Expected Behavior | Endpoint | Failure Mode | Feedback | Obvious? | Safe? | QA Risk |
|--------|----------|-------------------|----------|--------------|----------|----------|-------|---------|
| **Save** | Onboarding overlay | Save name/timezone | Client-side localStorage | No server persistence | None | Yes | Yes | MEDIUM |
| **Skip for now** | Onboarding overlay | Dismiss onboarding | Client-side localStorage | Onboarding never re-appears | Poor — user loses setup path | Yes | Partially | HIGH |
| **▶ Try it now** | Guided tour overlay | Send example command | cmdSend() | Command may fail | OK | Yes | Yes | LOW |
| **Got it** | Guided tour | Dismiss guided tour | Client-side | Tour never shows again | Poor | Yes | Yes | MEDIUM |

---

## 12. Dead / Duplicate / Misleading Buttons Summary

### Dead Buttons (No visible effect)
- **"📅 Plan my day"** action button — sends chat message, creates no tasks
- **"✅ Create tasks"** action button — sends chat message, creates no tasks
- **"🎙 Voice"** in Commander Brief — sends text command, not voice
- **"Focus"** (Executive Mode) — effect is invisible without specific layout

### Duplicate Buttons (Same action, different locations)
- "Compare Now" and "Compare vs Real" (both call same endpoint)
- "↻ Refresh" on cockpit header and "Reconnect" in error state (same call)
- "🎙 Voice" in chat top row and "🎙 Mic" in voice bar (same function)
- "↻" refresh buttons appear 15+ times with no differentiating labels

### Dangerous Buttons (No confirmation, destructive)
- **"⚠ Reset Lab"** — deletes all paper trading history
- **Email "Delete"** — irreversibly deletes email
- **Task "Delete"** — no confirmation
- **Meeting "Delete"** — no confirmation
- **Calendar Event "Delete"** — no confirmation
- **Life item "✕"** — no confirmation

### Misleading Buttons
- **"🎙 Voice"** in Commander Brief — sends text, not voice
- **"Subscribe"** in Outlook — unclear what subscription means
- **"Backfill"** in Memory — technical term with no explanation
- **"+ Record"** in AI Learning — unclear what is being recorded
- **"Run Audit"** in Trader Analysis — shows JSON dump, not a report

---

## 13. UX Improvements Required

| Priority | Button/Area | Fix |
|----------|-------------|-----|
| CRITICAL | Reset Lab | Add confirmation modal: "This will delete all paper trading history. Cannot be undone." |
| CRITICAL | Email Delete | Add confirmation: "Delete this email permanently?" |
| CRITICAL | Plan my day / Create tasks | Actually create tasks — or rename to "Chat about my day" |
| HIGH | "Ask" vs "Send" | Standardize to "Send" across all inputs |
| HIGH | "🎙 Voice" Commander Brief | Rename to "🎙 Speak Brief" or remove misleading icon |
| HIGH | Command result overlay | Add persistent chat log below command bar |
| HIGH | "↻ Refresh" buttons | Add specific labels: "↻ Refresh Portfolio", "↻ Reload News" |
| HIGH | Import Real | Add confirmation: "This replaces your paper portfolio with real holdings." |
| HIGH | + Record (AI Learning) | Add tooltip: "Record the actual outcome of this trade to improve AI predictions" |
| HIGH | Subscribe (Outlook) | Rename to "Enable Real-time Email" |
| HIGH | Backfill (Memory) | Rename to "Build Memory from History" |
| MEDIUM | Voice input buttons | Remove duplicate — keep one consistent voice input location |
| MEDIUM | Wake word | Add visual indicator (pulsing mic) when active |
| MEDIUM | Task/Meeting/Event delete | Add confirmation dialog for all |
| MEDIUM | + Add Node | Rename to "+ Add Memory" with explanation |
| MEDIUM | Run Audit | Show formatted audit report, not JSON dump |
| LOW | All "↻" buttons | Add tooltips on hover |
| LOW | Focus button | Add tooltip: "Hide non-essential panels for focused view" |
