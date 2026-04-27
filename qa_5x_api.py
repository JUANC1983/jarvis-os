"""Phase 5X — Live API smoke test for ALL dashboard endpoints."""
import urllib.request, json, time

BASE = 'http://localhost:8000'
results = []

def get(path, label, timeout=6):
    try:
        t0 = time.monotonic()
        with urllib.request.urlopen(f'{BASE}{path}', timeout=timeout) as r:
            data = json.loads(r.read())
            ms = int((time.monotonic() - t0) * 1000)
            ok = r.status == 200
            results.append((label, path, 'PASS' if ok else 'FAIL', ms, None))
            return data
    except Exception as e:
        results.append((label, path, 'FAIL', 0, str(e)[:60]))
        return {}

def post(path, payload, label):
    try:
        t0 = time.monotonic()
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(f'{BASE}{path}', data=data,
               headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
            ms = int((time.monotonic() - t0) * 1000)
            results.append((label, path, 'PASS', ms, None))
            return data
    except Exception as e:
        results.append((label, path, 'FAIL', 0, str(e)[:60]))
        return {}

def delete(path, label):
    try:
        req = urllib.request.Request(f'{BASE}{path}', method='DELETE')
        with urllib.request.urlopen(req, timeout=5) as r:
            results.append((label, path, 'PASS', 0, None))
    except Exception as e:
        results.append((label, path, 'FAIL', 0, str(e)[:60]))

# ROOT
get('/', 'Root health')

# HOME / OVERVIEW  (frontend uses /dashboard/ prefix for legacy routes)
get('/dashboard/home', 'Overview home data')
get('/dashboard/assets', 'Assets list')
get('/dashboard/system', 'System metrics')
get('/dashboard/pipeline', 'Pipeline status')
get('/dashboard/recommendations', 'Market recommendations', timeout=15)
get('/dashboard/agents', 'Agents list')
get('/api/news/feed', 'News feed')
get('/dashboard/golf', 'Golf data')
get('/api/markets/snapshot', 'Market snapshot')

# TASKS  (/dashboard/tasks is the correct POST endpoint)
post('/dashboard/tasks', {'text': '__test_task__', 'priority': 'medium'}, 'Create task')
d = get('/dashboard/home', 'Home after task')
tasks = d.get('tasks', [])
test_task = next((t for t in tasks if t.get('text') == '__test_task__'), None)
if test_task:
    tid = test_task.get('id', '')
    post(f'/dashboard/tasks/{tid}/toggle', {}, 'Toggle task')
    delete(f'/dashboard/tasks/{tid}', 'Delete task')
else:
    results.append(('Toggle task',  '/dashboard/tasks/<id>/toggle', 'SKIP', 0, 'task not found'))
    results.append(('Delete task',  '/dashboard/tasks/<id>',        'SKIP', 0, 'task not found'))

# MEETINGS
post('/dashboard/meetings', {'title': '__test_meeting__', 'time': '10:00'}, 'Create meeting')
d = get('/dashboard/home', 'Home after meeting')
meetings = d.get('meetings', [])
test_m = next((m for m in meetings if m.get('title') == '__test_meeting__'), None)
if test_m:
    mid = test_m.get('id', '')
    delete(f'/api/meetings/{mid}', 'Delete meeting')
else:
    results.append(('Delete meeting', '/api/meetings/<id>', 'SKIP', 0, 'meeting not found'))

# GOLF
get('/api/golf/courses', 'Golf courses library')
get('/api/golf/bag', 'Golf bag')
get('/api/golf/profile', 'Golf profile')

# CALENDAR
get('/api/calendar/events', 'Calendar events (day)')
get('/api/calendar/events?range=week', 'Calendar events (week)')

# PROJECTS
get('/api/projects', 'Projects list')
d = post('/api/projects', {'name': '__test_proj__', 'description': 'QA test'}, 'Create project')
pid = d.get('project', {}).get('id', '') or d.get('id', '')
if pid:
    get(f'/api/projects/{pid}/tasks', 'Project tasks')
    post(f'/api/projects/{pid}/task', {'title': 'QA test task', 'status': 'todo'}, 'Create project task')
    delete(f'/api/projects/{pid}', 'Delete project')
else:
    results.append(('Project tasks',       '/api/projects/<id>/tasks', 'SKIP', 0, 'project not created'))
    results.append(('Create project task', '/api/projects/<id>/task',  'SKIP', 0, 'project not created'))
    results.append(('Delete project',      '/api/projects/<id>',       'SKIP', 0, 'project not created'))

# MEMORY
get('/api/memory/context', 'Memory context')
get('/api/memory/history', 'Memory history')
get('/api/memory/stats', 'Memory stats')

# NOTIFICATIONS
get('/api/notifications', 'Notifications list')
get('/api/notifications/unread-count', 'Notifications unread count')

# ANALYTICS
get('/api/analytics/summary', 'Analytics summary')
get('/api/analytics/productivity', 'Analytics productivity')
get('/api/analytics/golf', 'Analytics golf')
get('/api/analytics/projects', 'Analytics projects')

# WOW
get('/api/wow/insights', 'WOW insights')
get('/api/wow/briefing', 'WOW briefing')
get('/api/wow/suggestions', 'WOW suggestions')

# VOICE
get('/api/voice/status', 'Voice status')
get('/api/voice/settings', 'Voice settings')
get('/api/voice/history', 'Voice history')
post('/api/voice/command', {'transcript': 'test command', 'source': 'text'}, 'Voice command')

# GOLF VISION
get('/api/golf/vision/history', 'Golf vision history')
get('/api/golf/vision/drills', 'Golf vision drills')

# CHAT
post('/chat', {'message': 'hello test', 'domain': 'general'}, 'Chat endpoint')

# ORCHESTRATOR
get('/api/orchestrator/health', 'Orchestrator health')
post('/api/orchestrator/chat', {'message': 'what tasks do I have?'}, 'Orchestrator chat')

# AUTOMATIONS
get('/api/automations', 'Automations list')
get('/api/automations/stats', 'Automations stats')

# INTEGRATIONS
get('/api/integrations/status', 'Integrations status')

# PRINT RESULTS
print('=' * 72)
print(f'{"Label":<36} {"Path":<28} {"Status":<6} {"ms":>5}')
print('-' * 72)
passed = failed = skipped = 0
for label, path, status, ms, err in results:
    if status == 'PASS':
        flag = 'OK'; passed += 1
    elif status == 'SKIP':
        flag = '--'; skipped += 1
    else:
        flag = 'XX'; failed += 1
    extra = f'  [{err}]' if err else ''
    short_path = path[:27] if len(path) > 27 else path
    print(f'{flag} {label:<34} {short_path:<28} {status:<6} {ms:>4}ms{extra}')

print('=' * 72)
print(f'TOTAL: {passed+failed+skipped} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}')
