#!/usr/bin/env node

/**
 * Agent Simulator
 *
 * Simulates agent behavior for testing the swarm validation runner.
 * In a real implementation, this would be replaced by actual agent processes.
 */

import { randomInt } from 'crypto';
import { performance } from 'perf_hooks';

class AgentSimulator {
  constructor(agentName, config) {
    this.agentName = agentName;
    this.config = config;
    this.startTime = Date.now();
    this.taskCount = 0;
    this.running = true;

    // Agent behavior patterns based on type
    this.behaviors = {
      'coordinator': this.coordinatorBehavior.bind(this),
      'worker': this.workerBehavior.bind(this)
    };

    console.log(`🤖 Agent ${agentName} initialized with config:`, config);
  }

  async start() {
    console.log(`🚀 Starting agent ${this.agentName}...`);

    // Set up graceful shutdown
    process.on('SIGTERM', () => {
      console.log(`📡 Agent ${this.agentName} received SIGTERM, shutting down...`);
      this.running = false;
    });

    process.on('SIGINT', () => {
      console.log(`📡 Agent ${this.agentName} received SIGINT, shutting down...`);
      this.running = false;
    });

    // Start agent behavior
    const behavior = this.behaviors[this.config.type] || this.workerBehavior.bind(this);
    await behavior();

    console.log(`🔚 Agent ${this.agentName} completed execution`);
  }

  async coordinatorBehavior() {
    console.log(`📋 ${this.agentName} acting as coordinator for ${this.config.stream} stream...`);

    // Simulate coordination tasks
    const coordinationTasks = [
      'initialize-stream',
      'coordinate-agents',
      'monitor-progress',
      'handle-failures',
      'aggregate-results'
    ];

    for (const task of coordinationTasks) {
      if (!this.running) break;

      console.log(`🎯 ${this.agentName}: Executing coordination task: ${task}`);
      await this.simulateTaskExecution(task, 2000, 5000); // 2-5 seconds per task

      // Emit coordination metrics
      this.emitMetric('coordination-task-completed', task);
      this.emitMetric('stream-progress', Math.random() * 20); // 0-20% progress
    }

    // Final coordination - signal completion
    console.log(`✅ ${this.agentName}: Stream coordination completed`);
    this.emitMetric('stream-completed', this.config.stream);
    this.emitMetric('truth-score', 0.95 + Math.random() * 0.04); // 95-99% truth score
  }

  async workerBehavior() {
    console.log(`⚙️ ${this.agentName} acting as worker in ${this.config.stream} stream...`);

    // Simulate worker tasks based on stream type
    const workerTasks = this.getWorkerTasks();

    for (const task of workerTasks) {
      if (!this.running) break;

      console.log(`🔧 ${this.agentName}: Executing worker task: ${task.name}`);

      // Simulate task execution
      const taskStartTime = performance.now();
      await this.simulateTaskExecution(task.name, task.minDuration, task.maxDuration);
      const taskDuration = performance.now() - taskStartTime;

      // Report task completion
      this.reportTaskCompletion(task.name, taskDuration);
      this.taskCount++;

      // Emit worker metrics
      this.emitMetric('task-completed', task.name);
      this.emitMetric('task-duration', taskDuration);
      this.emitMetric('tasks-total', this.taskCount);

      // Simulate occasional truth score updates
      if (this.taskCount % 3 === 0) {
        const truthScore = 0.90 + Math.random() * 0.09; // 90-99% truth score
        this.emitMetric('truth-score', truthScore);
      }

      // Small delay between tasks
      await this.sleep(1000);
    }

    // Report final metrics
    this.emitMetric('worker-completed', this.agentName);
    this.emitMetric('total-tasks', this.taskCount);
    this.emitMetric('truth-score', 0.94 + Math.random() * 0.05); // 94-99% final truth score
  }

  getWorkerTasks() {
    const taskTemplates = {
      'command-validation': [
        { name: 'validate-pair-commands', minDuration: 3000, maxDuration: 7000 },
        { name: 'validate-optimization-commands', minDuration: 4000, maxDuration: 8000 },
        { name: 'validate-monitoring-commands', minDuration: 2000, maxDuration: 5000 },
        { name: 'test-edge-cases', minDuration: 5000, maxDuration: 10000 },
        { name: 'validate-boundary-conditions', minDuration: 3000, maxDuration: 6000 }
      ],
      'agent-functionality': [
        { name: 'test-core-agents', minDuration: 5000, maxDuration: 12000 },
        { name: 'test-communication-protocols', minDuration: 4000, maxDuration: 8000 },
        { name: 'validate-memory-management', minDuration: 6000, maxDuration: 15000 },
        { name: 'test-neural-patterns', minDuration: 8000, maxDuration: 20000 },
        { name: 'validate-agent-coordination', minDuration: 7000, maxDuration: 18000 }
      ],
      'integration-testing': [
        { name: 'test-mcp-integration', minDuration: 4000, maxDuration: 9000 },
        { name: 'validate-github-workflows', minDuration: 6000, maxDuration: 14000 },
        { name: 'test-api-endpoints', minDuration: 3000, maxDuration: 7000 },
        { name: 'validate-authentication', minDuration: 5000, maxDuration: 11000 },
        { name: 'test-data-integrity', minDuration: 4000, maxDuration: 8000 }
      ],
      'performance-testing': [
        { name: 'benchmark-concurrent-execution', minDuration: 8000, maxDuration: 20000 },
        { name: 'monitor-memory-usage', minDuration: 6000, maxDuration: 15000 },
        { name: 'test-cpu-utilization', minDuration: 5000, maxDuration: 12000 },
        { name: 'validate-scalability', minDuration: 10000, maxDuration: 25000 },
        { name: 'test-resource-cleanup', minDuration: 3000, maxDuration: 7000 }
      ]
    };

    return taskTemplates[this.config.stream] || [
      { name: 'generic-task', minDuration: 3000, maxDuration: 8000 }
    ];
  }

  async simulateTaskExecution(taskName, minDuration, maxDuration) {
    const duration = randomInt(minDuration, maxDuration);
    const steps = 10;
    const stepDuration = duration / steps;

    console.log(`⏳ ${this.agentName}: Starting ${taskName} (estimated ${duration}ms)...`);

    for (let i = 0; i < steps && this.running; i++) {
      // Simulate work being done
      await this.sleep(stepDuration);

      // Emit progress update
      const progress = ((i + 1) / steps) * 100;
      console.log(`📈 ${this.agentName}: ${taskName} progress: ${progress.toFixed(1)}%`);
      this.emitMetric('task-progress', { task: taskName, progress });
    }

    if (this.running) {
      console.log(`✅ ${this.agentName}: Completed ${taskName}`);
    } else {
      console.log(`⏹️ ${this.agentName}: Interrupted ${taskName}`);
    }
  }

  reportTaskCompletion(taskName, duration) {
    console.log(`TASK_COMPLETED:${taskName}:${duration.toFixed(2)}`);

    // Report task result
    const success = Math.random() > 0.05; // 95% success rate
    if (success) {
      console.log(`METRIC:${JSON.stringify({ type: 'task-success', value: taskName })}`);
    } else {
      console.log(`METRIC:${JSON.stringify({ type: 'task-failure', value: taskName })}`);
    }
  }

  emitMetric(type, value) {
    const metric = {
      type,
      value,
      timestamp: new Date().toISOString(),
      agent: this.agentName
    };
    console.log(`METRIC:${JSON.stringify(metric)}`);
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

// Main execution
async function main() {
  const agentName = process.argv[2];
  const configStr = process.argv[3];

  if (!agentName || !configStr) {
    console.error('❌ Usage: node agent-simulator.js <agent-name> <config-json>');
    process.exit(1);
  }

  try {
    const config = JSON.parse(configStr);
    const agent = new AgentSimulator(agentName, config);
    await agent.start();
  } catch (error) {
    console.error(`❌ Agent ${agentName} failed:`, error);
    process.exit(1);
  }
}

// Run if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}