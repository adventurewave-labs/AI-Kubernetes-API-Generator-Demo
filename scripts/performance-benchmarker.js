#!/usr/bin/env node

/**
 * Comprehensive Performance Testing Suite
 * Tests system performance across multiple dimensions
 */

import { performance } from 'perf_hooks';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import os from 'os';

class PerformanceBenchmarker {
  constructor() {
    this.results = {
      timestamp: new Date().toISOString(),
      systemSpecs: {},
      baseline: {},
      benchmarks: {},
      stressTests: {},
      resourceUsage: [],
      concurrentTests: {}
    };
    this.monitoringInterval = null;
  }

  async runComprehensiveBenchmarks() {
    console.log('🚀 Starting Comprehensive Performance Testing Suite');
    console.log('=' .repeat(60));

    try {
      // 1. System Analysis
      await this.analyzeSystemSpecs();

      // 2. Baseline Performance
      await this.establishBaseline();

      // 3. Command Performance Tests
      await this.benchmarkCommandExecution();

      // 4. File Operation Performance
      await this.benchmarkFileOperations();

      // 5. Concurrent Operation Tests
      await this.benchmarkConcurrentOperations();

      // 6. Stress Testing
      await this.runStressTests();

      // 7. Generate Report
      await this.generateComprehensiveReport();

    } catch (error) {
      console.error('❌ Benchmark suite failed:', error);
      throw error;
    }
  }

  async analyzeSystemSpecs() {
    console.log('📊 Analyzing System Specifications...');

    const specs = {
      platform: process.platform,
      arch: process.arch,
      nodeVersion: process.version,
      memory: {
        total: os.totalmem(),
        free: os.freemem(),
        usage: ((os.totalmem() - os.freemem()) / os.totalmem() * 100).toFixed(2) + '%'
      },
      cpu: {
        model: await this.getCPUModel(),
        cores: os.cpus().length,
        loadAverage: os.loadavg()
      },
      disk: await this.getDiskUsage()
    };

    this.results.systemSpecs = specs;
    console.log('✅ System specs captured:', JSON.stringify(specs, null, 2));
  }

  async getCPUModel() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/proc/cpuinfo']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const match = output.match(/model name\s*:\s*(.+)/);
        resolve(match ? match[1].trim() : 'Unknown');
      });
    });
  }

  async getDiskUsage() {
    return new Promise((resolve) => {
      const child = spawn('df', ['-h', '/workspaces']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        if (lines.length > 1) {
          const parts = lines[1].split(/\s+/);
          resolve({
            size: parts[1],
            used: parts[2],
            available: parts[3],
            usage: parts[4]
          });
        }
        resolve({});
      });
    });
  }

  async establishBaseline() {
    console.log('📈 Establishing Baseline Performance Metrics...');

    const baseline = {
      processStartup: await this.measureProcessStartup(),
      simpleMath: await this.measureSimpleMath(),
      stringOperations: await this.measureStringOperations(),
      arrayOperations: await this.measureArrayOperations(),
      objectOperations: await this.measureObjectOperations()
    };

    this.results.baseline = baseline;
    console.log('✅ Baseline metrics established');
  }

  async measureProcessStartup() {
    const iterations = 10;
    const times = [];

    for (let i = 0; i < iterations; i++) {
      const start = performance.now();
      await new Promise(resolve => {
        const child = spawn('node', ['-e', 'console.log("test")']);
        child.on('close', resolve);
      });
      times.push(performance.now() - start);
    }

    return {
      mean: times.reduce((a, b) => a + b) / times.length,
      min: Math.min(...times),
      max: Math.max(...times),
      stdDev: this.calculateStdDev(times)
    };
  }

  async measureSimpleMath() {
    const iterations = 100000;
    const times = [];

    for (let i = 0; i < 10; i++) {
      const start = performance.now();
      let result = 0;
      for (let j = 0; j < iterations; j++) {
        result += Math.sin(j) * Math.cos(j) + Math.sqrt(j);
      }
      times.push(performance.now() - start);
    }

    return {
      operationsPerSecond: iterations / (times.reduce((a, b) => a + b) / times.length),
      meanTime: times.reduce((a, b) => a + b) / times.length
    };
  }

  async measureStringOperations() {
    const iterations = 50000;
    const testString = 'Performance testing string operations ';

    const start = performance.now();
    let result = '';
    for (let i = 0; i < iterations; i++) {
      result += testString + i.toString();
      result = result.toUpperCase();
      result = result.toLowerCase();
    }
    const time = performance.now() - start;

    return {
      operationsPerSecond: iterations * 3 / time,
      totalTime: time
    };
  }

  async measureArrayOperations() {
    const iterations = 10000;
    const testArray = Array.from({length: 1000}, (_, i) => i);

    const operations = {
      map: () => testArray.map(x => x * 2),
      filter: () => testArray.filter(x => x % 2 === 0),
      reduce: () => testArray.reduce((a, b) => a + b, 0),
      sort: () => [...testArray].sort((a, b) => b - a)
    };

    const results = {};
    for (const [op, fn] of Object.entries(operations)) {
      const start = performance.now();
      for (let i = 0; i < iterations / 100; i++) {
        fn();
      }
      results[op] = performance.now() - start;
    }

    return results;
  }

  async measureObjectOperations() {
    const iterations = 10000;
    const testObject = {};

    // Build test object
    for (let i = 0; i < 1000; i++) {
      testObject[`key${i}`] = i;
    }

    const start = performance.now();
    let result = 0;
    for (let i = 0; i < iterations; i++) {
      for (const key in testObject) {
        result += testObject[key];
      }
    }
    const time = performance.now() - start;

    return {
      operationsPerSecond: iterations * 1000 / time,
      totalTime: time
    };
  }

  async benchmarkCommandExecution() {
    console.log('⚡ Benchmarking Command Execution...');

    const commands = [
      { name: 'ls', args: ['-la'] },
      { name: 'find', args: ['/workspaces', '-name', '*.js', '|', 'head', '-5'] },
      { name: 'grep', args: ['-r', 'function', '/workspaces', '|', 'head', '-5'] },
      { name: 'node', args: ['-e', 'console.log("Hello World")'] },
      { name: 'npm', args: ['--version'] }
    ];

    const results = {};

    for (const cmd of commands) {
      console.log(`  Testing: ${cmd.name} ${cmd.args.join(' ')}`);
      results[cmd.name] = await this.benchmarkSingleCommand(cmd);
    }

    this.results.benchmarks.commandExecution = results;
    console.log('✅ Command execution benchmarks completed');
  }

  async benchmarkSingleCommand(command) {
    const iterations = 5;
    const times = [];
    const successes = [];

    for (let i = 0; i < iterations; i++) {
      const start = performance.now();
      try {
        await new Promise((resolve, reject) => {
          const child = spawn(command.name, command.args.filter(arg => arg !== '|'));
          let output = '';
          child.stdout.on('data', (data) => output += data.toString());
          child.stderr.on('data', (data) => output += data.toString());
          child.on('close', (code) => {
            if (code === 0) resolve(output);
            else reject(new Error(`Command failed with code ${code}`));
          });
        });
        times.push(performance.now() - start);
        successes.push(true);
      } catch (error) {
        times.push(performance.now() - start);
        successes.push(false);
      }
    }

    return {
      meanTime: times.reduce((a, b) => a + b) / times.length,
      minTime: Math.min(...times),
      maxTime: Math.max(...times),
      successRate: successes.filter(Boolean).length / successes.length,
      iterations: iterations
    };
  }

  async benchmarkFileOperations() {
    console.log('📁 Benchmarking File Operations...');

    const testDir = '/tmp/perf-test';
    const testFile = path.join(testDir, 'test.txt');
    const testContent = 'Performance testing content '.repeat(1000);

    // Ensure test directory exists
    await this.execCommand('mkdir', ['-p', testDir]);

    const operations = {
      writeSmall: () => this.writeFile(testFile, 'small content'),
      writeLarge: () => this.writeFile(testFile, testContent),
      readSmall: () => this.readFile(testFile),
      readLarge: () => this.readFile(testFile),
      copyFile: () => this.execCommand('cp', [testFile, testFile + '.copy']),
      deleteFile: () => this.execCommand('rm', [testFile + '.copy'])
    };

    const results = {};

    for (const [op, fn] of Object.entries(operations)) {
      console.log(`  Testing: ${op}`);
      const start = performance.now();
      await fn();
      results[op] = performance.now() - start;
    }

    this.results.benchmarks.fileOperations = results;
    console.log('✅ File operation benchmarks completed');

    // Cleanup
    await this.execCommand('rm', ['-rf', testDir]);
  }

  async writeFile(filePath, content) {
    return new Promise((resolve, reject) => {
      fs.writeFile(filePath, content, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async readFile(filePath) {
    return new Promise((resolve, reject) => {
      fs.readFile(filePath, 'utf8', (err, data) => {
        if (err) reject(err);
        else resolve(data);
      });
    });
  }

  async execCommand(cmd, args) {
    return new Promise((resolve, reject) => {
      const child = spawn(cmd, args);
      child.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`Command failed: ${cmd}`));
      });
    });
  }

  async benchmarkConcurrentOperations() {
    console.log('🔄 Benchmarking Concurrent Operations...');

    const concurrentLevels = [1, 2, 4, 8, 16];
    const results = {};

    for (const level of concurrentLevels) {
      console.log(`  Testing concurrency level: ${level}`);

      const start = performance.now();
      const promises = [];

      for (let i = 0; i < level; i++) {
        promises.push(this.simulateWorkload(i));
      }

      await Promise.all(promises);
      const totalTime = performance.now() - start;

      results[level] = {
        totalTime,
        averageTimePerTask: totalTime / level,
        throughput: level / (totalTime / 1000) // tasks per second
      };
    }

    this.results.concurrentTests = results;
    console.log('✅ Concurrent operation benchmarks completed');
  }

  async simulateWorkload(taskId) {
    // Simulate mixed workload: CPU, I/O, and network operations
    const start = performance.now();

    // CPU work
    let result = 0;
    for (let i = 0; i < 100000; i++) {
      result += Math.sqrt(i) * Math.sin(i);
    }

    // Simulate I/O work
    await new Promise(resolve => setTimeout(resolve, Math.random() * 50));

    // More CPU work
    for (let i = 0; i < 50000; i++) {
      result = Math.pow(result, 0.5);
    }

    return performance.now() - start;
  }

  async runStressTests() {
    console.log('🔥 Running Stress Tests...');

    const stressTests = {
      memoryStress: await this.runMemoryStressTest(),
      cpuStress: await this.runCPUStressTest(),
      fileStress: await this.runFileStressTest()
    };

    this.results.stressTests = stressTests;
    console.log('✅ Stress tests completed');
  }

  async runMemoryStressTest() {
    console.log('  Running memory stress test...');

    const objects = [];
    const start = performance.now();
    let iteration = 0;

    try {
      while (iteration < 1000) { // Limit iterations for safety
        // Allocate memory
        objects.push({
          data: new Array(1000).fill(Math.random()),
          timestamp: Date.now(),
          id: iteration
        });

        iteration++;

        // Check memory usage every 100 iterations
        if (iteration % 100 === 0) {
          const memUsage = process.memoryUsage();
          console.log(`    Iteration ${iteration}: Memory usage: ${Math.round(memUsage.heapUsed / 1024 / 1024)}MB`);

          // Stop if we're using too much memory
          if (memUsage.heapUsed > 500 * 1024 * 1024) { // 500MB limit
            break;
          }
        }
      }
    } catch (error) {
      console.log(`    Memory stress test stopped at iteration ${iteration}: ${error.message}`);
    }

    const totalTime = performance.now() - start;
    const finalMemory = process.memoryUsage();

    return {
      iterations: iteration,
      totalTime,
      objectsCreated: objects.length,
      finalMemoryUsage: finalMemory.heapUsed,
      memoryGrowthRate: iteration > 0 ? finalMemory.heapUsed / iteration : 0
    };
  }

  async runCPUStressTest() {
    console.log('  Running CPU stress test...');

    const duration = 5000; // 5 seconds
    const start = performance.now();
    let operations = 0;

    while (performance.now() - start < duration) {
      // CPU-intensive operations
      for (let i = 0; i < 1000; i++) {
        Math.sqrt(Math.random() * 1000000);
        operations++;
      }
    }

    const totalTime = performance.now() - start;

    return {
      duration: totalTime,
      operations,
      operationsPerSecond: operations / (totalTime / 1000)
    };
  }

  async runFileStressTest() {
    console.log('  Running file stress test...');

    const testDir = '/tmp/file-stress-test';
    await this.execCommand('mkdir', ['-p', testDir]);

    const start = performance.now();
    const files = [];

    try {
      for (let i = 0; i < 100; i++) {
        const fileName = path.join(testDir, `stress_${i}.txt`);
        const content = `Stress test file ${i}\n${'Data line '.repeat(100)}`;

        await this.writeFile(fileName, content);
        files.push(fileName);

        // Read back some files to stress I/O
        if (i % 10 === 0 && i > 0) {
          await this.readFile(files[Math.floor(i / 2)]);
        }
      }
    } catch (error) {
      console.log(`    File stress test stopped: ${error.message}`);
    }

    const totalTime = performance.now() - start;

    // Cleanup
    await this.execCommand('rm', ['-rf', testDir]);

    return {
      filesCreated: files.length,
      totalTime,
      filesPerSecond: files.length / (totalTime / 1000)
    };
  }

  calculateStdDev(values) {
    const mean = values.reduce((a, b) => a + b) / values.length;
    const squaredDiffs = values.map(value => Math.pow(value - mean, 2));
    const avgSquaredDiff = squaredDiffs.reduce((a, b) => a + b) / squaredDiffs.length;
    return Math.sqrt(avgSquaredDiff);
  }

  async generateComprehensiveReport() {
    console.log('📋 Generating Comprehensive Performance Report...');

    const reportPath = '/workspaces/ai-kubernetes-api-generator-demo/docs/PERFORMANCE_ANALYSIS_REPORT.md';

    const report = `# Comprehensive Performance Analysis Report

Generated: ${new Date().toISOString()}

## System Specifications

**Platform:** ${this.results.systemSpecs.platform} (${this.results.systemSpecs.arch})
**Node.js Version:** ${this.results.systemSpecs.nodeVersion}
**CPU:** ${this.results.systemSpecs.cpu?.model || 'Unknown'} (${this.results.systemSpecs.cpu?.cores} cores)
**Memory:** ${Math.round(this.results.systemSpecs.memory?.total / 1024 / 1024 / 1024)}GB total (${this.results.systemSpecs.memory?.usage} used)
**Disk:** ${this.results.systemSpecs.disk?.size || 'Unknown'} (${this.results.systemSpecs.disk?.usage || 'Unknown'} used)

## Baseline Performance Metrics

### Process Startup Performance
- **Mean Time:** ${this.results.baseline.processStartup?.mean?.toFixed(2)}ms
- **Min Time:** ${this.results.baseline.processStartup?.min?.toFixed(2)}ms
- **Max Time:** ${this.results.baseline.processStartup?.max?.toFixed(2)}ms

### Mathematical Operations
- **Operations/Second:** ${Math.round(this.results.baseline.simpleMath?.operationsPerSecond || 0)}

### String Operations
- **Operations/Second:** ${Math.round(this.results.baseline.stringOperations?.operationsPerSecond || 0)}

### Array Operations Performance
${Object.entries(this.results.baseline.arrayOperations || {}).map(([op, time]) =>
  `- **${op}:** ${time.toFixed(2)}ms`
).join('\n')}

### Object Operations
- **Operations/Second:** ${Math.round(this.results.baseline.objectOperations?.operationsPerSecond || 0)}

## Command Execution Benchmarks

${Object.entries(this.results.benchmarks.commandExecution || {}).map(([cmd, results]) =>
`### ${cmd.toUpperCase()}
- **Mean Time:** ${results.meanTime?.toFixed(2)}ms
- **Success Rate:** ${(results.successRate * 100).toFixed(1)}%
- **Min/Max:** ${results.minTime?.toFixed(2)}ms / ${results.maxTime?.toFixed(2)}ms`
).join('\n\n')}

## File Operation Benchmarks

${Object.entries(this.results.benchmarks.fileOperations || {}).map(([op, time]) =>
`- **${op}:** ${time.toFixed(2)}ms`
).join('\n')}

## Concurrent Operation Performance

${Object.entries(this.results.concurrentTests || {}).map(([level, results]) =>
`### Concurrency Level: ${level}
- **Total Time:** ${results.totalTime?.toFixed(2)}ms
- **Average Time/Task:** ${results.averageTimePerTask?.toFixed(2)}ms
- **Throughput:** ${results.throughput?.toFixed(2)} tasks/second`
).join('\n')}

## Stress Test Results

### Memory Stress Test
- **Objects Created:** ${this.results.stressTests.memoryStress?.objectsCreated || 0}
- **Final Memory Usage:** ${Math.round((this.results.stressTests.memoryStress?.finalMemoryUsage || 0) / 1024 / 1024)}MB
- **Memory Growth Rate:** ${Math.round(this.results.stressTests.memoryStress?.memoryGrowthRate || 0)} bytes/object

### CPU Stress Test
- **Duration:** ${this.results.stressTests.cpuStress?.duration?.toFixed(2)}ms
- **Operations:** ${this.results.stressTests.cpuStress?.operations || 0}
- **Operations/Second:** ${Math.round(this.results.stressTests.cpuStress?.operationsPerSecond || 0)}

### File Stress Test
- **Files Created:** ${this.results.stressTests.fileStress?.filesCreated || 0}
- **Total Time:** ${this.results.stressTests.fileStress?.totalTime?.toFixed(2)}ms
- **Files/Second:** ${Math.round(this.results.stressTests.fileStress?.filesPerSecond || 0)}

## Performance Analysis & Recommendations

### Key Findings

1. **System Capacity:** The system demonstrates ${this.analyzeSystemCapacity()}
2. **Concurrency Performance:** ${this.analyzeConcurrencyPerformance()}
3. **Resource Efficiency:** ${this.analyzeResourceEfficiency()}

### Performance Optimization Recommendations

1. **CPU Optimization:**
   ${this.generateCPURecommendations()}

2. **Memory Optimization:**
   ${this.generateMemoryRecommendations()}

3. **I/O Optimization:**
   ${this.generateIORecommendations()}

4. **Concurrency Optimization:**
   ${this.generateConcurrencyRecommendations()}

### Bottleneck Analysis

${this.identifyBottlenecks()}

## Scaling Recommendations

${this.generateScalingRecommendations()}

## Monitoring Recommendations

${this.generateMonitoringRecommendations()}

---

**Report generated by Performance Benchmarker**
**All metrics are based on controlled test conditions**
`;

    await this.writeFile(reportPath, report);

    // Also save raw results as JSON
    const jsonPath = reportPath.replace('.md', '.json');
    await this.writeFile(jsonPath, JSON.stringify(this.results, null, 2));

    console.log(`✅ Comprehensive report generated: ${reportPath}`);
    console.log(`📊 Raw data saved: ${jsonPath}`);
  }

  analyzeSystemCapacity() {
    const cpuOps = this.results.baseline.simpleMath?.operationsPerSecond || 0;
    const memUsage = this.results.systemSpecs.memory?.total || 0;

    if (cpuOps > 1000000) return 'excellent computational capacity';
    if (cpuOps > 500000) return 'good computational capacity';
    return 'moderate computational capacity';
  }

  analyzeConcurrencyPerformance() {
    const results = this.results.concurrentTests;
    if (!results || Object.keys(results).length === 0) return 'No concurrency data available';

    const throughputs = Object.values(results).map(r => r.throughput || 0);
    const maxThroughput = Math.max(...throughputs);
    const optimalLevel = Object.entries(results).find(([_, r]) => r.throughput === maxThroughput)?.[0] || 'unknown';

    return `Optimal concurrency level is ${optimalLevel} with ${maxThroughput.toFixed(2)} tasks/second`;
  }

  analyzeResourceEfficiency() {
    const memStress = this.results.stressTests.memoryStress;
    if (!memStress) return 'No memory efficiency data available';

    const growthRate = memStress.memoryGrowthRate || 0;
    if (growthRate < 1000) return 'excellent memory efficiency';
    if (growthRate < 5000) return 'good memory efficiency';
    return 'memory efficiency could be improved';
  }

  generateCPURecommendations() {
    const cpuStress = this.results.stressTests.cpuStress;
    if (!cpuStress) return '- No CPU performance data available';

    const opsPerSec = cpuStress.operationsPerSecond || 0;
    if (opsPerSec > 100000) {
      return '- CPU performance is excellent\n- Consider implementing CPU-intensive optimizations\n- Monitor CPU usage under load';
    } else if (opsPerSec > 50000) {
      return '- CPU performance is good\n- Consider algorithmic optimizations for CPU-bound tasks';
    } else {
      return '- CPU performance may need attention\n- Profile CPU-bound operations\n- Consider more efficient algorithms';
    }
  }

  generateMemoryRecommendations() {
    const memStress = this.results.stressTests.memoryStress;
    if (!memStress) return '- No memory performance data available';

    const growthRate = memStress.memoryGrowthRate || 0;
    if (growthRate < 1000) {
      return '- Memory usage is efficient\n- Current memory management is optimal';
    } else if (growthRate < 5000) {
      return '- Memory usage is acceptable\n- Consider memory pooling for frequently allocated objects';
    } else {
      return '- Memory usage could be optimized\n- Implement memory pooling\n- Review object lifecycle management\n- Consider memory profiling tools';
    }
  }

  generateIORecommendations() {
    const fileOps = this.results.benchmarks.fileOperations;
    if (!fileOps) return '- No I/O performance data available';

    return '- Consider implementing async I/O operations\n- Use file system caching strategies\n- Batch file operations when possible\n- Consider compression for large file operations';
  }

  generateConcurrencyRecommendations() {
    const concurrent = this.results.concurrentTests;
    if (!concurrent) return '- No concurrency data available';

    const throughputs = Object.values(concurrent).map(r => r.throughput || 0);
    const maxThroughput = Math.max(...throughputs);

    if (maxThroughput > 100) {
      return '- Concurrency performance is excellent\n- Current threading model is effective';
    } else if (maxThroughput > 50) {
      return '- Concurrency performance is good\n- Consider load balancing strategies';
    } else {
      return '- Concurrency could be improved\n- Review blocking operations\n- Consider async patterns';
    }
  }

  identifyBottlenecks() {
    const bottlenecks = [];

    // Check if command execution is slow
    const cmdTimes = Object.values(this.results.benchmarks.commandExecution || {}).map(r => r.meanTime || 0);
    const avgCmdTime = cmdTimes.reduce((a, b) => a + b, 0) / cmdTimes.length;
    if (avgCmdTime > 1000) {
      bottlenecks.push('- Command execution appears to be a bottleneck (avg > 1s)');
    }

    // Check memory efficiency
    const memGrowth = this.results.stressTests.memoryStress?.memoryGrowthRate || 0;
    if (memGrowth > 5000) {
      bottlenecks.push('- Memory allocation growth rate is high');
    }

    // Check file operations
    const fileTimes = Object.values(this.results.benchmarks.fileOperations || {});
    const maxFileTime = Math.max(...Object.values(fileTimes));
    if (maxFileTime > 100) {
      bottlenecks.push('- File operations may be a bottleneck');
    }

    if (bottlenecks.length === 0) {
      bottlenecks.push('- No significant bottlenecks identified');
    }

    return bottlenecks.join('\n');
  }

  generateScalingRecommendations() {
    return `
### Horizontal Scaling
- Deploy multiple instances for load distribution
- Implement load balancing strategies
- Consider container orchestration (Kubernetes)

### Vertical Scaling
- Monitor CPU and memory utilization
- Scale based on performance metrics
- Consider resource allocation optimization

### Performance Monitoring
- Implement continuous performance monitoring
- Set up alerts for performance degradation
- Regularly benchmark and compare against baselines
`;
  }

  generateMonitoringRecommendations() {
    return `
### Key Metrics to Monitor
- CPU utilization and load averages
- Memory usage patterns and garbage collection
- I/O wait times and disk utilization
- Network latency and throughput
- Application response times

### Monitoring Tools
- Use application performance monitoring (APM) solutions
- Implement custom metrics collection
- Set up automated performance regression detection
- Use real-time monitoring dashboards

### Alerting Thresholds
- CPU usage > 80% for sustained periods
- Memory usage > 85% of available
- Response times > 2x baseline
- Error rates > 1%
`;
  }
}

// Run the comprehensive benchmark suite
if (import.meta.url === `file://${process.argv[1]}`) {
  const benchmarker = new PerformanceBenchmarker();
  benchmarker.runComprehensiveBenchmarks()
    .then(() => {
      console.log('\n🎉 Comprehensive Performance Testing Completed Successfully!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ Performance Testing Failed:', error);
      process.exit(1);
    });
}

export default PerformanceBenchmarker;