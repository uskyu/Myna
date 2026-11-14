"""Task Board API routes with self-contained schema and CRUD helpers."""
from datetime import datetime
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


router = APIRouter()


def _db(request: Request):
    return request.app.state.db


def _ws(request: Request):
    return request.app.state.ws_manager


def _row(db, row):
    return db._row_to_dict(row) if hasattr(db, '_row_to_dict') else dict(row)


def _rows(db, rows):
    return [_row(db, r) for r in rows]


def _ensure_schema(db):
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'normal',
            assigned_agent TEXT DEFAULT NULL,
            total_steps INTEGER DEFAULT 1,
            completed_steps INTEGER DEFAULT 0,
            metadata TEXT DEFAULT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_room ON tasks(room_id, status)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(assigned_agent, status)")
    db.commit()


def _list_tasks(db, room_id):
    _ensure_schema(db)
    ph = db._placeholder()
    return _rows(db, db.fetchall(
        "SELECT * FROM tasks WHERE room_id = " + ph + " ORDER BY "
        "CASE status WHEN 'in_progress' THEN 0 WHEN 'pending' THEN 1 "
        "WHEN 'failed' THEN 2 WHEN 'completed' THEN 3 END, created_at DESC",
        (room_id,),
    ))


def _get_task(db, task_id):
    _ensure_schema(db)
    ph = db._placeholder()
    row = db.fetchone("SELECT * FROM tasks WHERE id = " + ph, (task_id,))
    return _row(db, row) if row else None


def _create_task(db, room_id, body):
    _ensure_schema(db)
    ph = db._placeholder()
    db.execute(
        "INSERT INTO tasks (room_id, title, description, assigned_agent, priority, total_steps) "
        "VALUES (" + ph + ", " + ph + ", " + ph + ", " + ph + ", " + ph + ", " + ph + ")",
        (
            room_id,
            body.get('title', '').strip(),
            body.get('description', ''),
            body.get('assigned_agent'),
            body.get('priority', 'normal'),
            body.get('total_steps', 1),
        ),
    )
    db.commit()
    return _get_task(db, db.lastrowid())


def _update_task(db, task_id, body):
    _ensure_schema(db)
    ph = db._placeholder()
    allowed = ['title', 'description', 'status', 'priority', 'assigned_agent', 'total_steps', 'completed_steps', 'metadata']
    sets = []
    values = []
    for key in allowed:
        if key in body and body[key] is not None:
            value = json.dumps(body[key], ensure_ascii=False) if key == 'metadata' and not isinstance(body[key], str) else body[key]
            sets.append(key + ' = ' + ph)
            values.append(value)
    if sets:
        sets.append('updated_at = ' + db._now_func())
        values.append(task_id)
        db.execute('UPDATE tasks SET ' + ', '.join(sets) + ' WHERE id = ' + ph, values)
        db.commit()
    return _get_task(db, task_id)


def _delete_task(db, task_id):
    _ensure_schema(db)
    ph = db._placeholder()
    task = _get_task(db, task_id)
    if task:
        db.execute('DELETE FROM tasks WHERE id = ' + ph, (task_id,))
        db.commit()
    return task


def _analyze_stuck(task):
    if task.get('status') != 'in_progress':
        return None
    try:
        updated = datetime.fromisoformat(str(task.get('updated_at')).replace('Z', '+00:00'))
        minutes = max(0, int((datetime.now(updated.tzinfo) - updated).total_seconds() // 60))
    except Exception:
        minutes = 0
    return {
        'is_stuck': minutes >= 30,
        'minutes_since_update': minutes,
        'suggestion': '超过 30 分钟未更新，建议检查执行状态或重新分配。' if minutes >= 30 else '',
    }


def _enrich(tasks, request: Request):
    ws_manager = _ws(request)
    for task in tasks:
        active = None
        agent_id = task.get('assigned_agent')
        for stream in getattr(ws_manager, 'active_streams', {}).values():
            if agent_id and stream.get('agent_id') == agent_id and stream.get('room_id') == task.get('room_id'):
                active = stream
                break
        task['streaming'] = active is not None
        if active:
            task['stream_tool_calls'] = len(active.get('tool_calls', []))
            task['stream_text_preview'] = (active.get('text') or '')[:200]
        task['stuck_analysis'] = _analyze_stuck(task)
    return tasks


@router.get('/rooms/{room_id}/tasks')
async def list_tasks(room_id: str, request: Request):
    return {'ok': True, 'result': _enrich(_list_tasks(_db(request), room_id), request)}


@router.post('/rooms/{room_id}/tasks')
async def create_task(room_id: str, request: Request):
    body = await request.json()
    if not body.get('title', '').strip():
        return JSONResponse({'ok': False, 'error': 'title is required'}, status_code=400)
    task = _create_task(_db(request), room_id, body)
    await _ws(request).notify_ui({'type': 'task_created', 'room_id': room_id, 'task': task})
    return {'ok': True, 'result': task}


@router.patch('/tasks/{task_id}')
async def update_task(task_id: int, request: Request):
    db = _db(request)
    old = _get_task(db, task_id)
    if not old:
        return JSONResponse({'ok': False, 'error': 'Task not found'}, status_code=404)
    updated = _update_task(db, task_id, await request.json())
    await _ws(request).notify_ui({'type': 'task_updated', 'room_id': old['room_id'], 'task': updated})
    return {'ok': True, 'result': updated}


@router.delete('/tasks/{task_id}')
async def delete_task(task_id: int, request: Request):
    task = _delete_task(_db(request), task_id)
    if not task:
        return JSONResponse({'ok': False, 'error': 'Task not found'}, status_code=404)
    await _ws(request).notify_ui({'type': 'task_deleted', 'room_id': task['room_id'], 'task_id': task_id})
    return {'ok': True}


@router.get('/rooms/{room_id}/task-board')
async def get_task_board(room_id: str, request: Request):
    tasks = _enrich(_list_tasks(_db(request), room_id), request)
    return {
        'ok': True,
        'result': {
            'tasks': tasks,
            'board': {
                'pending': [t for t in tasks if t.get('status') == 'pending'],
                'in_progress': [t for t in tasks if t.get('status') == 'in_progress'],
                'completed': [t for t in tasks if t.get('status') == 'completed'],
                'failed': [t for t in tasks if t.get('status') == 'failed'],
            },
        },
    }
