
# Workflow Runner and Scheduler - Python port.
import json
import asyncio
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


class WorkflowRunner:
    def __init__(self, db, ws_manager):
        self.db = db
        self.ws_manager = ws_manager
        self.active_runs: dict[str, dict] = {}

    def _send_system_message(self, room_id: str, thread_id: str, text: str):
        self.db.ensure_system_agents()
        message = self.db.create_message(room_id, "system", text, "markdown", None, [], None, thread_id)
        asyncio.ensure_future(self.ws_manager.notify_ui({
            "type": "new_message",
            "room_id": room_id,
            "thread_id": thread_id,
            "message": {
                "id": message["id"],
                "room_id": room_id,
                "sender_id": "system",
                "sender_name": "系统",
                "text": text,
                "thread_id": thread_id,
                "created_at": datetime.now().isoformat(),
            }
        }))
        return message

    async def start(self, workflow_id: str, room_id: str) -> dict:
        workflow = self.db.get_workflow(workflow_id)
        if not workflow:
            raise ValueError("Workflow not found")
        if workflow.get("trigger_type") == "schedule":
            running_runs = [r for r in self.db.get_workflow_runs(workflow_id) if r.get("status") == "running"]
            if running_runs:
                raise RuntimeError(f"Workflow already running ({len(running_runs)} run(s))")

        run_count = self.db.get_workflow_run_count(workflow_id) + 1
        thread_title = f"流程: {workflow['name']} #{run_count}"

        thread = self.db.create_thread(room_id, thread_title, workflow_id)
        self.db.update_thread(thread["id"], {"status": "workflow_running"})

        run = self.db.create_workflow_run(workflow_id, thread["id"])
        self.active_runs[run["id"]] = {"cancelled": False}

        self._send_system_message(room_id, thread["id"], f"[系统] 🚀 开始执行流程「{workflow['name']}」")

        asyncio.create_task(self._execute_steps(run["id"], workflow, room_id, thread["id"]))

        return {"runId": run["id"], "threadId": thread["id"]}

    async def _execute_steps(self, run_id: str, workflow: dict, room_id: str, thread_id: str):
        steps = json.loads(workflow["steps_json"])
        total = len(steps)

        for i, step in enumerate(steps):
            state = self.active_runs.get(run_id)
            if state and state["cancelled"]:
                self._send_system_message(room_id, thread_id, "[系统] ⏹ 流程已取消")
                self.db.update_workflow_run(run_id, {"status": "cancelled", "completed_at": datetime.now().isoformat()})
                self.db.update_thread(thread_id, {"status": "active"})
                self.active_runs.pop(run_id, None)
                return

            try:
                await self._execute_step(run_id, workflow, room_id, thread_id, step, i + 1, total)
                self.db.update_workflow_run(run_id, {"current_step": i + 1})
                if i < total - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                self._send_system_message(room_id, thread_id, f"[系统] ❌ 步骤失败: {str(e)}")
                self.db.update_workflow_run(run_id, {"status": "failed", "completed_at": datetime.now().isoformat()})
                self.db.update_thread(thread_id, {"status": "active"})
                self.active_runs.pop(run_id, None)
                return

        self._send_system_message(room_id, thread_id, "[系统] ✅ 流程完成")
        self.db.update_workflow_run(run_id, {"status": "completed", "completed_at": datetime.now().isoformat()})
        self.db.update_thread(thread_id, {"status": "active"})
        self.active_runs.pop(run_id, None)

    async def _execute_step(self, run_id, workflow, room_id, thread_id, step, step_num, total):
        agent = self.db.get_agent_by_id(step["agent_id"])
        agent_name = agent["name"] if agent else step["agent_id"]

        self._send_system_message(room_id, thread_id, f"[系统] 步骤 {step_num}/{total} → @{agent_name}：{step['prompt']}")
        await asyncio.sleep(0.3)

        self.db.ensure_system_agents()
        prompt_msg = self.db.create_message(room_id, "user", step["prompt"], "markdown", None,
                                            [step["agent_id"]], None, thread_id)
        prompt_msg_id = prompt_msg.get("id")
        await self.ws_manager.notify_ui({
            "type": "new_message",
            "room_id": room_id,
            "thread_id": thread_id,
            "message": {
                "id": prompt_msg["id"],
                "room_id": room_id,
                "sender_id": "user",
                "sender_name": "我",
                "text": step["prompt"],
                "thread_id": thread_id,
                "created_at": datetime.now().isoformat(),
            }
        })

        from ai_engine import process_message
        await process_message(self.db, self.ws_manager, room_id, "user", step["prompt"],
                              [step["agent_id"]], "group", 0, thread_id)

        if step.get("wait_for_reply", True):
            start = asyncio.get_event_loop().time()
            timeout = max(300, step.get("timeout", 600))
            while asyncio.get_event_loop().time() - start < timeout:
                state = self.active_runs.get(run_id)
                if state and state["cancelled"]:
                    return
                msgs = self.db.get_thread_messages(thread_id, 200)
                for msg in msgs:
                    if msg["sender_id"] == step["agent_id"] and (prompt_msg_id is None or msg.get("id", 0) > prompt_msg_id):
                        return
                await asyncio.sleep(2)
            raise TimeoutError(f"等待 @{agent_name} 回复超时（{timeout}秒）")

    def cancel(self, run_id: str):
        state = self.active_runs.get(run_id)
        if state:
            state["cancelled"] = True
        else:
            run = self.db.get_workflow_run(run_id)
            if run and run["status"] == "running":
                self.db.update_workflow_run(run_id, {"status": "cancelled", "completed_at": datetime.now().isoformat()})


class WorkflowScheduler:
    def __init__(self, db, workflow_runner: WorkflowRunner):
        self.db = db
        self.runner = workflow_runner
        self.timezone = ZoneInfo("Asia/Shanghai") if ZoneInfo else timezone(timedelta(hours=8))
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)

    def start(self):
        self.scheduler.start()
        self.reload()
        print("[Scheduler] Started")

    def stop(self):
        self.scheduler.shutdown(wait=False)

    def reload(self):
        self.scheduler.remove_all_jobs()
        scheduled_count = 0
        rooms = self.db.list_rooms()
        for room in rooms:
            workflows = self.db.get_workflows(room["id"])
            for wf in workflows:
                if wf["trigger_type"] == "schedule":
                    if self._schedule_workflow(wf):
                        scheduled_count += 1
        print(f"[Scheduler] Reloaded {scheduled_count} scheduled workflow(s)")

    def _schedule_workflow(self, wf: dict):
        try:
            config = json.loads(wf.get("trigger_config") or "{}")
        except Exception as e:
            print(f"[Scheduler] Invalid trigger_config for workflow {wf.get('id')}: {e}")
            config = {}

        trigger = None
        tz = self.timezone

        if config.get("cron"):
            try:
                parts = str(config["cron"]).split()
                trigger = CronTrigger(
                    minute=parts[0] if len(parts) > 0 else "*",
                    hour=parts[1] if len(parts) > 1 else "*",
                    day=parts[2] if len(parts) > 2 else "*",
                    month=parts[3] if len(parts) > 3 else "*",
                    day_of_week=parts[4] if len(parts) > 4 else "*",
                    timezone=tz,
                )
            except Exception as e:
                print(f"[Scheduler] Invalid cron for workflow {wf.get('id')}: {e}")
                return False
        elif config.get("interval_minutes"):
            trigger = IntervalTrigger(minutes=max(1, int(config["interval_minutes"])), timezone=tz)
        elif config.get("interval_hours"):
            trigger = IntervalTrigger(hours=max(1, int(config["interval_hours"])), timezone=tz)
        elif config.get("daily_time"):
            try:
                parts = str(config["daily_time"]).split(":")
                trigger = CronTrigger(hour=int(parts[0]), minute=int(parts[1]) if len(parts) > 1 else 0, timezone=tz)
            except Exception as e:
                print(f"[Scheduler] Invalid daily_time for workflow {wf.get('id')}: {e}")
                return False
        elif config.get("weekly_day") is not None:
            try:
                parts = str(config.get("weekly_time") or "09:00").split(":")
                day = int(config["weekly_day"])
                day_names = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
                trigger = CronTrigger(
                    day_of_week=day_names[day % 7],
                    hour=int(parts[0]),
                    minute=int(parts[1]) if len(parts) > 1 else 0,
                    timezone=tz,
                )
            except Exception as e:
                print(f"[Scheduler] Invalid weekly schedule for workflow {wf.get('id')}: {e}")
                return False

        if not trigger:
            print(f"[Scheduler] No trigger for workflow {wf.get('id')} config={config}")
            return False

        self.scheduler.add_job(
            self._trigger_workflow,
            trigger=trigger,
            args=[wf["id"], wf["room_id"]],
            id=f"workflow_{wf['id']}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=60,
        )
        job = self.scheduler.get_job(f"workflow_{wf['id']}")
        print(f"[Scheduler] Scheduled workflow {wf.get('id')} next_run={getattr(job, 'next_run_time', None)}")
        return True

    async def _trigger_workflow(self, workflow_id: str, room_id: str):
        try:
            workflow = self.db.get_workflow(workflow_id)
            if not workflow:
                print(f"[Scheduler] Workflow {workflow_id} no longer exists; removing stale job")
                try:
                    self.scheduler.remove_job(f"workflow_{workflow_id}")
                except Exception:
                    pass
                return
            if workflow.get("trigger_type") != "schedule":
                print(f"[Scheduler] Workflow {workflow_id} trigger_type={workflow.get('trigger_type')} is not schedule; removing stale job")
                try:
                    self.scheduler.remove_job(f"workflow_{workflow_id}")
                except Exception:
                    pass
                return
            await self.runner.start(workflow_id, room_id)
        except Exception as e:
            print(f"[Scheduler] Failed to run workflow {workflow_id}: {e}")
