# JARVIS Navigation & Information Architecture Audit
**Audit Date:** 2026-05-07  
**Verdict:** 18 tabs is not an IA — it is a list of engine files exposed as navigation.

---

## 1. Current Navigation Map

### Desktop Primary Navigation (18 visible tabs)
```
JARVIS OS
├── Overview          (all-in-one dashboard)
├── Markets           (sub-tabs: Cockpit / Paper Lab / AI Learning / Analysis)
├── Agents            (AI agent status)
├── Productivity      (tasks + meetings + uploads)
├── Calendar          (local + Microsoft calendar)
├── Projects          (project management + AI tasks)
├── Golf              (swing vision + caddie + courses + rounds)
├── Intelligence      (news feed)
├── Analytics         (productivity + portfolio + golf analytics)
├── Running           [HIDDEN — module-gated]
├── Cycling           [HIDDEN — module-gated]
├── Gym               [HIDDEN — module-gated]
├── Tennis            [HIDDEN — module-gated]
├── 🏠 Life           (reminders + shopping + calls + payments)
├── 📧 Outlook        (AI email processing)
├── ⚡ Automations    (triggers + actions)
├── 🧠 Memory         (graph memory + conversation history)
├── System            (agent pipeline + health checks)
└── Chat              (direct AI chat + voice)
```

### Mobile Bottom Navigation (8 shortcuts, overlapping with desktop)
```
🏠 Home | 📈 Markets | 💬 Chat | ✅ Tasks | 📅 Calendar | 📋 Projects | ⛳ Golf | 📰 Intel | ⚙️ System
```

### Markets Sub-Navigation (4 sub-tabs)
```
Markets tab
├── Cockpit     (real portfolio + risk overview)
├── Paper Lab   (simulation + performance)
├── AI Learning (calibration + outcome recording)
└── Analysis    (ticker analysis + recommendations + news)
```

### Golf Sub-tabs (inside Golf tab)
```
Golf tab
├── Swing Vision (camera + recording + analysis)
│   ├── Historia (history)
│   ├── Drills
│   └── Progreso (progress)
├── Caddie (club recommendation tool)
├── Course Library (search + details)
├── Golf Bag (equipment management)
└── Rounds (history + logging)
```

---

## 2. Critical Architecture Problems

### Problem 1: No Information Hierarchy
Every tab has equal visual weight. "Golf" and "Markets" are peers. "Memory" and "Calendar" are peers. There is no distinction between:
- Core daily workflows (Calendar, Tasks, Chat)
- Financial tools (Portfolio, Analysis)
- Leisure/lifestyle (Golf, Fitness)
- System tools (Agents, Memory, System)

### Problem 2: Tab Naming Is Engineer-First
| Current Name | What It Actually Is | Normal User Translation |
|-------------|--------------------|-----------------------|
| Agents | AI agent monitoring | "What's running" |
| Intelligence | News feed | "News" |
| Memory | Conversation history + graph | "What JARVIS knows" |
| System | Pipeline + health | "System status" |
| Analytics | Usage + productivity stats | "My insights" |
| Cockpit | Portfolio overview | "My Portfolio" |
| Paper Lab | Simulation trading | "Investment Simulator" |
| AI Learning | Model calibration | "AI Accuracy" |
| WoW Layer | Briefing section | "Daily Brief" |
| Commander Brief | Daily executive brief | "My Summary" |

### Problem 3: Duplicate Concepts Across Tabs
| Concept | Where It Appears (Duplicate) |
|---------|------------------------------|
| "What's happening today" | Overview Priority Center AND Commander Brief |
| News | Intelligence tab AND Analysis panel inside Markets |
| AI chat | Command bar (top) AND Chat tab |
| Calendar | Calendar tab AND Productivity tab (meetings section) |
| Portfolio status | Overview (tile) AND Markets (full panel) |
| Agent status | Overview (card) AND Agents tab (full panel) AND System tab |
| Analytics | Analytics tab AND inside Markets (paper performance) |

### Problem 4: Markets Tab Has 4 Sub-tabs That Are Each Different Products
The Markets tab currently contains:
- A real-time portfolio viewer (Cockpit)
- A paper trading simulator (Paper Lab)
- A machine learning dashboard (AI Learning)
- A stock analysis tool (Analysis)

These four are completely different tools that should be peer-level items, not nested sub-tabs under "Markets."

### Problem 5: Golf Has Depth But Markets Has Width
Golf module has logical sub-sections and users understand the hierarchy (swing → caddie → courses → rounds). Markets has 4 unrelated panels at the same level — structurally confusing.

### Problem 6: Hidden Fitness Tabs Have No Visible Entry Point
Four tabs (Running, Cycling, Gym, Tennis) are hidden by default. The only way to enable them is through a small "⚙ Modules" gear icon in the Overview section that is not labeled "Settings" or "Enable Modules." This creates a terrible discovery problem.

### Problem 7: No Settings Section
There is no "Settings" tab. Configuration is done via .env files only. Module management is buried in Overview. Voice settings are in Chat. Integration management is via API calls.

---

## 3. Recommended Navigation Map

### Core Principle: 3 Zones
```
Zone 1 — Daily Use    (always visible)
Zone 2 — Portfolio    (financial tools)
Zone 3 — More         (expandable, lifestyle/advanced)
```

### Proposed Desktop Navigation (5 primary tabs + expandable More)
```
JARVIS OS
├── 🏠 Home          (unified daily dashboard)
│   ├── Good morning brief
│   ├── Priority: Tasks + Meetings today
│   ├── Portfolio snapshot (1 tile)
│   ├── Recent news (1 tile)
│   └── Quick actions (Plan day / Chat / Analyze)
│
├── 💬 Chat          (AI assistant + voice)
│   ├── Chat history
│   ├── Voice controls
│   └── Quick suggestions
│
├── 📅 Planner       (calendar + tasks + projects)
│   ├── Calendar view (day/week/month)
│   ├── Tasks
│   ├── Meetings
│   └── Projects
│
├── 📈 Portfolio     (all financial in one place)
│   ├── Overview     (real account tiles)
│   ├── Simulator    (paper trading)
│   ├── Analysis     (ticker lookup + recommendations)
│   ├── AI Signals   (learning + calibration)
│   └── News         (financial news)
│
├── ⚙️ Settings      (all configuration)
│   ├── Connections  (Outlook, Calendar, IBKR)
│   ├── API Keys     (OpenAI, ElevenLabs)
│   ├── Voice        (language, provider)
│   ├── Modules      (enable/disable features)
│   ├── Notifications
│   └── Account
│
└── ··· More         (expandable section)
    ├── ⛳ Golf
    ├── 🏠 Life
    ├── ⚡ Automations
    ├── 🧠 Memory
    ├── 📊 Analytics
    ├── 📧 Outlook Inbox
    ├── 🏃 Fitness (Running, Cycling, Gym, Tennis)
    └── 🔧 System (for advanced users)
```

### Proposed Mobile Navigation (5 shortcuts)
```
🏠 Home | 💬 Chat | 📅 Planner | 📈 Portfolio | ··· More
```

---

## 4. Current vs Recommended: Tab Count

| Navigation | Count | Notes |
|------------|-------|-------|
| Current desktop primary | 15 visible tabs | Overwhelming |
| Current mobile | 9 shortcuts | Overlapping with desktop |
| Recommended desktop primary | 5 tabs | Clear zones |
| Recommended desktop expandable | 8 items in "More" | Discoverable |
| Recommended mobile | 5 shortcuts | Thumb-friendly |

---

## 5. User Journey Maps

### Simplified Daily-Use Journey (Normal User)
```
Morning routine:
Open JARVIS → Home tab (auto-loads)
→ Read "Good morning [name]" brief
→ See tasks for today
→ See next meeting
→ Quick-chat: "What should I focus on today?"
→ Done in 3 minutes
```

### Expert User Journey (Trader/Developer)
```
Trading session:
Open JARVIS → Portfolio tab
→ Check IBKR connection status
→ Review position P&L
→ Switch to Analysis → type ticker
→ Read setup score + narrative
→ Check AI Signals for calibration
→ Switch to Paper Lab → simulate entry
→ Return to Home to log insight in Chat
```

### First-Time Onboarding Journey (New User)
```
First launch:
Onboarding wizard → Enter name + timezone
→ Screen: "Connect your calendar" → [Connect Outlook] or [Skip]
→ Screen: "Connect your portfolio" → [IBKR guide] or [Use Simulator]
→ Screen: "You're ready" → [Take me to Home]
→ Home tab with 3 example commands shown
→ Day 1: try 3 quick actions
→ Day 3: explore Chat deeper
→ Day 7: enable Golf or Fitness modules
```

### Admin/Developer Journey
```
Deploy + configure:
Set .env → start server
→ Open /docs for API spec
→ Open System tab → check all agents green
→ Open Outlook → connect account
→ Test Chat → confirm LLM routing
→ Set up Automations
→ Daily: review audit logs
```

---

## 6. Information Architecture Improvements

### Immediate Wins (No code changes)
1. Rename "Agents" → "AI Status"
2. Rename "Intelligence" → "News"
3. Rename "System" → "System Health" (or move to Settings)
4. Rename "Memory" → "What JARVIS Knows"
5. Rename "Commander Brief" → "Your Daily Summary"
6. Rename "WoW Layer" → "Today's Insights"
7. Add subtitle under each tab button (on hover or always on desktop)

### Medium-Term (Moderate code changes)
1. Add a proper "Settings" tab consolidating:
   - Module management
   - API key configuration
   - Voice settings
   - Integration connections
2. Move Agents and System into Settings > Advanced
3. Add "More" expandable section for lifestyle modules
4. Consolidate News: remove from Analysis panel, keep only in Intelligence tab
5. Add sub-tabs to Planner: Calendar | Tasks | Meetings | Projects

### Long-Term (Major restructure)
1. Implement the 5-tab navigation architecture above
2. Move all Portfolio content under one Portfolio tab with proper sub-sections
3. Create proper onboarding wizard
4. Implement "Discover" section showing hidden/available modules
5. Add personalization: "Show tabs I use, hide the rest"

---

## 7. 10-Second Navigation Test

**Question:** Can a user find what they need in 10 seconds?

| Task | Seconds (current) | Findable? |
|------|------------------|-----------|
| Find chat | 2 | Yes — Chat tab visible |
| Add a task | 5 | Yes — Productivity tab |
| Check portfolio | 4 | Yes — Markets tab |
| Connect Outlook | 35+ | No — Outlook tab + OAuth flow unclear |
| Enable running tracker | 45+ | No — hidden behind Modules gear |
| View automations | 5 | Yes — Automations tab |
| Change voice language | 20+ | No — buried in Chat > Voice settings |
| View memory history | 10 | Borderline — Memory tab visible |
| Find IBKR connection status | 25+ | No — buried in System tab |
| Configure API keys | ∞ | Impossible — no UI exists |
