# Frontend-Backend Integration Audit

Generated at: 2026-05-21T06:49:23.458Z

## Summary

- Backend routes: 22
- Frontend API routes: 22
- Missing frontend route coverage: 0
- Extra frontend routes (not found in backend): 0
- Potentially unused API functions: 2

## Missing Frontend Route Coverage

- None

## Extra Frontend Routes

- None

## Potentially Unused API Functions

- createEventSource (src/api/client.ts)
- updatePage (src/api/pages.api.ts)

## Route Matrix

- DELETE /journals/{id} -> covered: yes
- DELETE /materials/upload/sessions/{id} -> covered: yes
- DELETE /pages/{id} -> covered: yes
- GET /ai/tasks/{id} -> covered: yes
- GET /ai/tasks/{id}/events -> covered: yes
- GET /journals -> covered: yes
- GET /journals/{id} -> covered: yes
- GET /materials -> covered: yes
- GET /materials/recommend -> covered: yes
- GET /pages/{id} -> covered: yes
- GET /preferences -> covered: yes
- GET /weather -> covered: yes
- POST /ai/tasks -> covered: yes
- POST /export -> covered: yes
- POST /journals -> covered: yes
- POST /materials/upload/sessions -> covered: yes
- POST /materials/upload/sessions/complete -> covered: yes
- POST /pages -> covered: yes
- POST /uploads/audio -> covered: yes
- POST /uploads/image -> covered: yes
- PUT /pages/{id} -> covered: yes
- PUT /preferences -> covered: yes

