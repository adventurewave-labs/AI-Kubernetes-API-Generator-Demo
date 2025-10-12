#!/usr/bin/env node

/**
 * Real-time System Resource Monitor
 * Monitors CPU, Memory, Disk, and Network usage during performance tests
 */

import { performance } from 'perf_hooks';
import { spawn } from 'child_process';
import fs from 'fs';
import os from 'os';

class ResourceMonitor {
  constructor() {
    this.monitoring = false;
    this.interval = null;
    this.metrics = {
      timestamp: new Date().toISOString(),
      samples: [],
      summary: {}
    };
    this.sampleCount = 0;
    this.maxSamples = 1000; // Limit memory usage
  }

  async startMonitoring(sampleIntervalMs = 1000) {
    if (this.monitoring) {
      console.log('⚠️  Resource monitoring already active');
      return;
    }

    console.log(`📊 Starting resource monitoring (interval: ${sampleIntervalMs}ms)`);
    this.monitoring = true;
    this.sampleCount = 0;

    // Take initial sample
    await this.takeSample();

    // Set up regular sampling
    this.interval = setInterval(async () => {
      await this.takeSample();
    }, sampleIntervalMs);

    return new Promise((resolve) => {
      this.startPromise = resolve;
    });
  }

  async takeSample() {
    const timestamp = Date.now();
    const sample = {
      timestamp,
      time: new Date(timestamp).toISOString(),
      cpu: await this.getCPUMetrics(),
      memory: await this.getMemoryMetrics(),
      disk: await this.getDiskMetrics(),
      network: await this.getNetworkMetrics(),
      processes: await this.getProcessMetrics()
    };

    this.metrics.samples.push(sample);
    this.sampleCount++;

    // Limit number of samples to prevent memory issues
    if (this.metrics.samples.length > this.maxSamples) {
      this.metrics.samples.shift();
    }

    // Log key metrics every 10 samples
    if (this.sampleCount % 10 === 0) {
      this.logKeyMetrics(sample);
    }

    return sample;
  }

  async getCPUMetrics() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/proc/stat']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        const cpuLine = lines.find(line => line.startsWith('cpu '));
        if (cpuLine) {
          const parts = cpuLine.split(/\s+/);
          const [user, nice, system, idle, iowait, irq, softirq] =
            parts.slice(1).map(Number);

          const total = user + nice + system + idle + iowait + irq + softirq;
          const used = total - idle;

          resolve({
            total,
            used,
            idle,
            usagePercent: ((used / total) * 100).toFixed(2),
            loadAverage: os.loadavg(),
            cores: os.cpus().length
          });
        } else {
          resolve({ usagePercent: '0', loadAverage: os.loadavg(), cores: os.cpus().length });
        }
      });
    });
  }

  async getMemoryMetrics() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/proc/meminfo']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        const memInfo = {};

        lines.forEach(line => {
          const match = line.match(/^(\w+):\s+(\d+)\s+kB$/);
          if (match) {
            memInfo[match[1]] = parseInt(match[2]) * 1024; // Convert to bytes
          }
        });

        const total = memInfo.MemTotal || 0;
        const available = memInfo.MemAvailable || 0;
        const used = total - available;
        const buffers = memInfo.Buffers || 0;
        const cached = memInfo.Cached || 0;
        const swapTotal = memInfo.SwapTotal || 0;
        const swapFree = memInfo.SwapFree || 0;
        const swapUsed = swapTotal - swapFree;

        resolve({
          total,
          used,
          available,
          usagePercent: ((used / total) * 100).toFixed(2),
          buffers,
          cached,
          swap: {
            total: swapTotal,
            used: swapUsed,
            free: swapFree,
            usagePercent: swapTotal > 0 ? ((swapUsed / swapTotal) * 100).toFixed(2) : '0'
          }
        });
      });
    });
  }

  async getDiskMetrics() {
    return new Promise((resolve) => {
      const child = spawn('df', ['-h', '/workspaces']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        if (lines.length > 1) {
          const parts = lines[1].split(/\s+/);
          resolve({
            filesystem: parts[0],
            size: parts[1],
            used: parts[2],
            available: parts[3],
            usagePercent: parts[4],
            mountpoint: parts[5]
          });
        } else {
          resolve({});
        }
      });
    });
  }

  async getNetworkMetrics() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/proc/net/dev']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        let totalRx = 0;
        let totalTx = 0;

        lines.slice(2).forEach(line => {
          if (line.trim()) {
            const parts = line.trim().split(/\s+/);
            const rxBytes = parseInt(parts[1]) || 0;
            const txBytes = parseInt(parts[9]) || 0;
            totalRx += rxBytes;
            totalTx += txBytes;
          }
        });

        resolve({
          rxBytes: totalRx,
          txBytes: totalTx,
          totalBytes: totalRx + totalTx,
          rxMB: (totalRx / 1024 / 1024).toFixed(2),
          txMB: (totalTx / 1024 / 1024).toFixed(2)
        });
      });
    });
  }

  async getProcessMetrics() {
    const nodeProcess = process.memoryUsage();
    return {
      pid: process.pid,
      nodeMemory: {
        rss: nodeProcess.rss,
        heapUsed: nodeProcess.heapUsed,
        heapTotal: nodeProcess.heapTotal,
        external: nodeProcess.external,
        arrayBuffers: nodeProcess.arrayBuffers
      },
      uptime: process.uptime(),
      cpuUsage: process.cpuUsage()
    };
  }

  logKeyMetrics(sample) {
    console.log(`📊 Sample ${this.sampleCount}: CPU: ${sample.cpu.usagePercent}% | Memory: ${sample.memory.usagePercent}% | Disk: ${sample.disk.usagePercent} | Load: ${sample.cpu.loadAverage[0].toFixed(2)}`);
  }

  stopMonitoring() {
    if (!this.monitoring) {
      console.log('⚠️  Resource monitoring not active');
      return;
    }

    console.log('🛑 Stopping resource monitoring');
    this.monitoring = false;

    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }

    // Generate summary
    this.generateSummary();

    return this.metrics;
  }

  generateSummary() {
    if (this.metrics.samples.length === 0) {
      console.log('⚠️  No samples to analyze');
      return;
    }

    const samples = this.metrics.samples;

    // CPU Analysis
    const cpuUsages = samples.map(s => parseFloat(s.cpu.usagePercent));
    const cpuSummary = {
      avg: (cpuUsages.reduce((a, b) => a + b, 0) / cpuUsages.length).toFixed(2),
      max: Math.max(...cpuUsages).toFixed(2),
      min: Math.min(...cpuUsages).toFixed(2),
      samples: cpuUsages.length
    };

    // Memory Analysis
    const memUsages = samples.map(s => parseFloat(s.memory.usagePercent));
    const memSummary = {
      avg: (memUsages.reduce((a, b) => a + b, 0) / memUsages.length).toFixed(2),
      max: Math.max(...memUsages).toFixed(2),
      min: Math.min(...memUsages).toFixed(2),
      peakMemory: Math.max(...samples.map(s => s.memory.used))
    };

    // Load Average Analysis
    const loadAvgs = samples.map(s => s.cpu.loadAverage[0]);
    const loadSummary = {
      avg: (loadAvgs.reduce((a, b) => a + b, 0) / loadAvgs.length).toFixed(2),
      max: Math.max(...loadAvgs).toFixed(2),
      min: Math.min(...loadAvgs).toFixed(2)
    };

    this.metrics.summary = {
      duration: samples.length > 1 ?
        (samples[samples.length - 1].timestamp - samples[0].timestamp) / 1000 : 0,
      samples: samples.length,
      cpu: cpuSummary,
      memory: memSummary,
      loadAverage: loadSummary,
      timestamp: new Date().toISOString()
    };

    console.log('\n📊 Resource Monitoring Summary:');
    console.log(`  Duration: ${this.metrics.summary.duration}s`);
    console.log(`  Samples: ${this.metrics.summary.samples}`);
    console.log(`  CPU: Avg ${cpuSummary.avg}% | Max ${cpuSummary.max}% | Min ${cpuSummary.min}%`);
    console.log(`  Memory: Avg ${memSummary.avg}% | Max ${memSummary.max}% | Min ${memSummary.min}%`);
    console.log(`  Load Avg: Avg ${loadSummary.avg} | Max ${loadSummary.max} | Min ${loadSummary.min}`);
  }

  async saveResults(outputPath) {
    const report = `# Resource Monitoring Report

Generated: ${new Date().toISOString()}

## Monitoring Summary

- **Duration:** ${this.metrics.summary.duration}s
- **Samples Collected:** ${this.metrics.summary.samples}
- **Sampling Interval:** ~1000ms

## CPU Performance

- **Average Usage:** ${this.metrics.summary.cpu.avg}%
- **Peak Usage:** ${this.metrics.summary.cpu.max}%
- **Minimum Usage:** ${this.metrics.summary.cpu.min}%
- **CPU Cores:** ${this.metrics.samples[0]?.cpu?.cores || 'N/A'}

## Memory Performance

- **Average Usage:** ${this.metrics.summary.memory.avg}%
- **Peak Usage:** ${this.metrics.summary.memory.max}%
- **Minimum Usage:** ${this.metrics.summary.memory.min}%
- **Peak Memory Usage:** ${Math.round(this.metrics.summary.memory.peakMemory / 1024 / 1024)}MB

## Load Average

- **Average 1-min Load:** ${this.metrics.summary.loadAverage.avg}
- **Peak 1-min Load:** ${this.metrics.summary.loadAverage.max}
- **Minimum 1-min Load:** ${this.metrics.summary.loadAverage.min}

## Performance Analysis

### CPU Analysis
${this.analyzeCPUPerformance()}

### Memory Analysis
${this.analyzeMemoryPerformance()}

### System Health
${this.analyzeSystemHealth()}

## Recommendations

${this.generateRecommendations()}

---

*Report generated by Resource Monitor*
`;

    await fs.promises.writeFile(outputPath, report);

    // Also save raw data
    const jsonPath = outputPath.replace('.md', '.json');
    await fs.promises.writeFile(jsonPath, JSON.stringify(this.metrics, null, 2));

    console.log(`📋 Resource monitoring report saved: ${outputPath}`);
    console.log(`📊 Raw data saved: ${jsonPath}`);
  }

  analyzeCPUPerformance() {
    const avgCPU = parseFloat(this.metrics.summary.cpu.avg);
    const maxCPU = parseFloat(this.metrics.summary.cpu.max);

    if (maxCPU > 90) {
      return '⚠️  **High CPU Usage Detected**: System experienced periods of heavy CPU load. Consider investigating CPU-intensive processes.';
    } else if (avgCPU > 70) {
      return '🟡 **Moderate CPU Usage**: System maintained moderate CPU usage throughout monitoring period.';
    } else {
      return '✅ **Healthy CPU Usage**: CPU usage remained within acceptable limits.';
    }
  }

  analyzeMemoryPerformance() {
    const avgMem = parseFloat(this.metrics.summary.memory.avg);
    const maxMem = parseFloat(this.metrics.summary.memory.max);

    if (maxMem > 90) {
      return '⚠️  **High Memory Usage**: System experienced periods of high memory usage. Monitor for memory leaks.';
    } else if (avgMem > 70) {
      return '🟡 **Moderate Memory Usage**: Memory usage was moderate throughout monitoring period.';
    } else {
      return '✅ **Healthy Memory Usage**: Memory usage remained within acceptable limits.';
    }
  }

  analyzeSystemHealth() {
    const avgLoad = parseFloat(this.metrics.summary.loadAverage.avg);
    const cores = this.metrics.samples[0]?.cpu?.cores || 1;
    const loadPerCore = avgLoad / cores;

    if (loadPerCore > 2) {
      return '⚠️  **High System Load**: Load average significantly exceeds CPU cores. System may be overloaded.';
    } else if (loadPerCore > 1) {
      return '🟡 **Moderate System Load**: Load average is moderate relative to CPU capacity.';
    } else {
      return '✅ **Healthy System Load**: Load average is within normal limits for available CPU cores.';
    }
  }

  generateRecommendations() {
    const recommendations = [];

    const avgCPU = parseFloat(this.metrics.summary.cpu.avg);
    const maxCPU = parseFloat(this.metrics.summary.cpu.max);
    const avgMem = parseFloat(this.metrics.summary.memory.avg);
    const maxMem = parseFloat(this.metrics.summary.memory.max);

    if (maxCPU > 90) {
      recommendations.push('- **CPU Optimization**: Profile CPU-intensive operations and consider algorithmic improvements');
    }

    if (maxMem > 85) {
      recommendations.push('- **Memory Management**: Implement memory monitoring and investigate potential memory leaks');
    }

    if (avgCPU > 70 || avgMem > 70) {
      recommendations.push('- **Resource Monitoring**: Set up continuous monitoring with alerts for high resource usage');
    }

    recommendations.push('- **Baseline Establishment**: Use this data as a baseline for future performance comparisons');
    recommendations.push('- **Regular Monitoring**: Schedule regular resource monitoring during different workload patterns');

    return recommendations.join('\n');
  }
}

// Command line interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const monitor = new ResourceMonitor();

  // Parse command line arguments
  const args = process.argv.slice(2);
  const duration = parseInt(args.find(arg => arg.startsWith('--duration='))?.split('=')[1] || '30');
  const output = args.find(arg => arg.startsWith('--output='))?.split('=')[1] || '/workspaces/ai-kubernetes-api-generator-demo/docs/RESOURCE_MONITORING_REPORT.md';

  console.log(`🚀 Starting resource monitoring for ${duration} seconds`);

  await monitor.startMonitoring(1000);

  // Stop after specified duration
  setTimeout(() => {
    const results = monitor.stopMonitoring();
    monitor.saveResults(output);
    console.log('✅ Resource monitoring completed');
    process.exit(0);
  }, duration * 1000);
}

export default ResourceMonitor;