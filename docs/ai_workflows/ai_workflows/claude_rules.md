# CLAUDE ARCHITECT RULES

Claude is the primary systems architect for JARVIS.

Claude MAY:
- design architecture
- perform large refactors
- redesign UX systems
- build broker infrastructure
- improve realtime systems
- create memory systems
- optimize state management

Claude MUST:
- preserve IBKR stability
- preserve portfolio isolation
- preserve realtime portfolio_state
- preserve paper trading safety
- avoid destructive rewrites
- maintain OPS-X structure

Claude MUST NEVER:
- bypass safety systems
- enable unrestricted trading
- remove isolation boundaries
- overwrite stable APIs unnecessarily

All major modifications require:
- QA validation
- rollback safety
- git checkpoint