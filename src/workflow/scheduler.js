/**
 * WorkflowScheduler
 * Uses node-cron for precise scheduling and a fallback interval check.
 * On startup, loads all workflows with cron/schedule triggers and schedules them.
 */

const cron = require('node-cron');

class WorkflowScheduler {
  constructor(db, workflowRunner) {
    this.db = db;
    this.workflowRunner = workflowRunner;
    this.scheduledWorkflows = [];
    this.cronJobs = new Map(); // workflowId -> cron.ScheduledTask
    this.lastRunAt = new Map(); // workflowId -> Date
    this.intervalId = null;
  }

  /**
   * Start the scheduler - loads workflows and schedules cron jobs.
   */
  async start() {
    await this.reload();
    // Fallback interval check every 60s for any missed triggers
    this.intervalId = setInterval(() => this._check(), 60 * 1000);
    console.log('[Scheduler] Started with node-cron, fallback check every 60s');
  }

  /**
   * Stop the scheduler.
   */
  stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    // Stop all cron jobs
    for (const [id, job] of this.cronJobs) {
      job.stop();
    }
    this.cronJobs.clear();
  }

  /**
   * Reload all scheduled workflows from DB and reschedule cron jobs.
   */
  async reload() {
    try {
      // Stop existing cron jobs
      for (const [id, job] of this.cronJobs) {
        job.stop();
      }
      this.cronJobs.clear();

      // Get all workflows, then filter for schedule type
      const allRooms = await this.db.listRooms();
      const scheduled = [];
      for (const room of allRooms) {
        const workflows = this.db.getWorkflows(room.id);
        for (const wf of workflows) {
          if (wf.trigger_type === 'schedule') {
            scheduled.push(wf);
          }
        }
      }
      this.scheduledWorkflows = scheduled;

      // Initialize last_run_at from latest workflow_run for each
      for (const wf of scheduled) {
        if (!this.lastRunAt.has(wf.id)) {
          const runs = this.db.getWorkflowRuns ? this.db.getWorkflowRuns(wf.id) : [];
          if (runs.length > 0) {
            const latest = runs[0]; // Assuming sorted by started_at DESC
            this.lastRunAt.set(wf.id, new Date(latest.started_at));
          }
        }
      }

      // Schedule cron jobs for each workflow
      for (const wf of scheduled) {
        this._scheduleCronJob(wf);
      }

      console.log(`[Scheduler] Loaded ${scheduled.length} scheduled workflow(s), ${this.cronJobs.size} cron job(s) active`);
    } catch (err) {
      console.error('[Scheduler] reload error:', err.message);
    }
  }

  /**
   * Schedule a cron job for a workflow based on its trigger_config.
   */
  _scheduleCronJob(wf) {
    try {
      const config = typeof wf.trigger_config === 'string'
        ? JSON.parse(wf.trigger_config || '{}')
        : (wf.trigger_config || {});

      let cronExpression = null;

      // If user provided a raw cron expression
      if (config.cron) {
        cronExpression = config.cron;
      }
      // Interval-based: every N hours -> run at minute 0 every N hours
      else if (config.interval_hours) {
        const hours = Math.max(1, Math.min(24, config.interval_hours));
        if (hours === 1) {
          cronExpression = '0 * * * *'; // Every hour at minute 0
        } else {
          cronExpression = `0 */${hours} * * *`; // Every N hours at minute 0
        }
      }
      // Daily at specific time
      else if (config.daily_time) {
        const [hours, minutes] = config.daily_time.split(':').map(Number);
        cronExpression = `${minutes || 0} ${hours || 9} * * *`;
      }
      // Weekly: specific day + time
      else if (config.weekly_day !== undefined && config.weekly_time) {
        const [hours, minutes] = config.weekly_time.split(':').map(Number);
        cronExpression = `${minutes || 0} ${hours || 9} * * ${config.weekly_day}`;
      }

      if (cronExpression && cron.validate(cronExpression)) {
        const job = cron.schedule(cronExpression, () => {
          this._triggerWorkflow(wf);
        }, { scheduled: true });
        this.cronJobs.set(wf.id, job);
      }
    } catch (err) {
      console.error(`[Scheduler] Failed to schedule cron for workflow ${wf.id}:`, err.message);
    }
  }

  /**
   * Trigger a workflow run.
   */
  _triggerWorkflow(wf) {
    console.log(`[Scheduler] Triggering workflow "${wf.name}" (${wf.id})`);
    this.lastRunAt.set(wf.id, new Date());
    this.workflowRunner.start(wf.id, wf.room_id).catch(err => {
      console.error(`[Scheduler] Failed to run workflow ${wf.id}:`, err.message);
    });
  }

  /**
   * Add a workflow to the scheduler.
   */
  add(workflow) {
    if (workflow.trigger_type === 'schedule') {
      this.scheduledWorkflows.push(workflow);
      this._scheduleCronJob(workflow);
    }
  }

  /**
   * Remove a workflow from the scheduler.
   */
  remove(workflowId) {
    this.scheduledWorkflows = this.scheduledWorkflows.filter(w => w.id !== workflowId);
    this.lastRunAt.delete(workflowId);
    const job = this.cronJobs.get(workflowId);
    if (job) {
      job.stop();
      this.cronJobs.delete(workflowId);
    }
  }

  /**
   * Fallback check for workflows that might not have cron jobs
   * (e.g., if cron expression was invalid).
   */
  _check() {
    const now = new Date();

    for (const wf of this.scheduledWorkflows) {
      // Skip if already has a cron job
      if (this.cronJobs.has(wf.id)) continue;

      try {
        const config = typeof wf.trigger_config === 'string'
          ? JSON.parse(wf.trigger_config || '{}')
          : (wf.trigger_config || {});

        if (this._isDue(wf.id, config, now)) {
          this._triggerWorkflow(wf);
        }
      } catch (err) {
        console.error(`[Scheduler] Error checking workflow ${wf.id}:`, err.message);
      }
    }
  }

  /**
   * Determine if a workflow is due to run (fallback logic).
   */
  _isDue(workflowId, config, now) {
    const lastRun = this.lastRunAt.get(workflowId);

    // Interval-based: every N hours
    if (config.interval_hours) {
      const intervalMs = config.interval_hours * 60 * 60 * 1000;
      if (!lastRun) return true;
      return (now.getTime() - lastRun.getTime()) >= intervalMs;
    }

    // Daily at specific time
    if (config.daily_time) {
      const [hours, minutes] = config.daily_time.split(':').map(Number);
      const nowH = now.getHours();
      const nowM = now.getMinutes();

      if (nowH === hours && nowM === minutes) {
        if (!lastRun) return true;
        const lastRunDate = lastRun.toDateString();
        const todayDate = now.toDateString();
        return lastRunDate !== todayDate;
      }
      return false;
    }

    // Weekly: specific day + time
    if (config.weekly_day !== undefined && config.weekly_time) {
      const [hours, minutes] = config.weekly_time.split(':').map(Number);
      const nowDay = now.getDay();
      const nowH = now.getHours();
      const nowM = now.getMinutes();

      if (nowDay === config.weekly_day && nowH === hours && nowM === minutes) {
        if (!lastRun) return true;
        const diffMs = now.getTime() - lastRun.getTime();
        return diffMs >= 6 * 24 * 60 * 60 * 1000;
      }
      return false;
    }

    return false;
  }
}

module.exports = WorkflowScheduler;
