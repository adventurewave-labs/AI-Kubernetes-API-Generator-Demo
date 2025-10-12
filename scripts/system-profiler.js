#!/usr/bin/env node

/**
 * Advanced System Profiler
 * Deep system analysis and bottleneck identification
 */

import { performance } from 'perf_hooks';
import { spawn } from 'child_process';
import fs from 'fs';
import os from 'os';

class SystemProfiler {
  constructor() {
    this.profileData = {
      timestamp: new Date().toISOString(),
      systemInfo: {},
      performanceProfile: {},
      bottleneckAnalysis: {},
      optimizationSuggestions: {},
      healthCheck: {}
    };
  }

  async runComprehensiveProfile() {
    console.log('🔬 Starting Comprehensive System Profiling...');
    console.log('=' .repeat(60));

    try {
      // System Information Collection
      await this.collectSystemInformation();

      // Performance Profiling
      await this.performPerformanceProfiling();

      // Bottleneck Analysis
      await this.analyzeBottlenecks();

      // System Health Check
      await this.performSystemHealthCheck();

      // Generate Optimization Suggestions
      await this.generateOptimizationSuggestions();

      // Create Profile Report
      await this.createProfileReport();

    } catch (error) {
      console.error('❌ System profiling failed:', error);
      throw error;
    }
  }

  async collectSystemInformation() {
    console.log('📊 Collecting System Information...');

    const systemInfo = {
      hardware: await this.getHardwareInfo(),
      software: await this.getSoftwareInfo(),
      network: await this.getNetworkInfo(),
      storage: await this.getStorageInfo(),
      processes: await this.getProcessInfo()
    };

    this.profileData.systemInfo = systemInfo;
    console.log('✅ System information collected');
  }

  async getHardwareInfo() {
    return {
      cpu: {
        model: await this.getCPUModel(),
        cores: os.cpus().length,
        architecture: os.arch(),
        frequency: await this.getCPUFrequency(),
        cache: await this.getCPUCache()
      },
      memory: {
        total: os.totalmem(),
        available: os.freemem(),
        modules: await this.getMemoryModules()
      },
      motherboard: await this.getMotherboardInfo()
    };
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

  async getCPUFrequency() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/proc/cpuinfo']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const match = output.match(/cpu MHz\s*:\s*(.+)/);
        resolve(match ? parseFloat(match[1].trim()) : 0);
      });
    });
  }

  async getCPUCache() {
    return new Promise((resolve) => {
      const child = spawn('lscpu');
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const l1d = output.match(/L1d cache:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const l1i = output.match(/L1i cache:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const l2 = output.match(/L2 cache:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const l3 = output.match(/L3 cache:\s*(.+)/)?.[1]?.trim() || 'Unknown';

        resolve({ l1d, l1i, l2, l3 });
      });
    });
  }

  async getMemoryModules() {
    return new Promise((resolve) => {
      const child = spawn('dmidecode', ['-t', 'memory']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const modules = [];
        const sections = output.split(/Memory Device\n/);

        sections.forEach(section => {
          if (section.includes('Size:') && !section.includes('No Module Installed')) {
            const size = section.match(/Size:\s*(.+)/)?.[1]?.trim();
            const type = section.match(/Type:\s*(.+)/)?.[1]?.trim();
            const speed = section.match(/Speed:\s*(.+)/)?.[1]?.trim();

            if (size && type) {
              modules.push({ size, type, speed });
            }
          }
        });

        resolve(modules);
      });
    });
  }

  async getMotherboardInfo() {
    return new Promise((resolve) => {
      const child = spawn('dmidecode', ['-t', 'baseboard']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const manufacturer = output.match(/Manufacturer:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const product = output.match(/Product Name:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const version = output.match(/Version:\s*(.+)/)?.[1]?.trim() || 'Unknown';

        resolve({ manufacturer, product, version });
      });
    });
  }

  async getSoftwareInfo() {
    return {
      os: {
        platform: process.platform,
        release: os.release(),
        version: await this.getOSVersion(),
        kernel: await this.getKernelVersion()
      },
      node: {
        version: process.version,
        dependencies: await this.getNodeDependencies()
      },
      runtime: {
        uptime: os.uptime(),
        loadAverage: os.loadavg(),
        memoryUsage: process.memoryUsage()
      }
    };
  }

  async getOSVersion() {
    return new Promise((resolve) => {
      const child = spawn('lsb_release', ['-a']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const distributor = output.match(/Distributor ID:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const description = output.match(/Description:\s*(.+)/)?.[1]?.trim() || 'Unknown';
        const release = output.match(/Release:\s*(.+)/)?.[1]?.trim() || 'Unknown';

        resolve({ distributor, description, release });
      });
    });
  }

  async getKernelVersion() {
    return new Promise((resolve) => {
      const child = spawn('uname', ['-r']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => resolve(output.trim()));
    });
  }

  async getNodeDependencies() {
    try {
      const packageJson = JSON.parse(await fs.promises.readFile('/workspaces/ai-kubernetes-api-generator-demo/package.json', 'utf8'));
      return {
        production: Object.keys(packageJson.dependencies || {}),
        development: Object.keys(packageJson.devDependencies || {})
      };
    } catch (error) {
      return { production: [], development: [] };
    }
  }

  async getNetworkInfo() {
    return {
      interfaces: await this.getNetworkInterfaces(),
      connections: await this.getActiveConnections(),
      dns: await this.getDNSInfo()
    };
  }

  async getNetworkInterfaces() {
    const interfaces = os.networkInterfaces();
    const result = {};

    for (const [name, addrs] of Object.entries(interfaces)) {
      result[name] = addrs.map(addr => ({
        address: addr.address,
        netmask: addr.netmask,
        family: addr.family,
        mac: addr.mac,
        internal: addr.internal
      }));
    }

    return result;
  }

  async getActiveConnections() {
    return new Promise((resolve) => {
      const child = spawn('ss', ['-tuln']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n').slice(1);
        const connections = lines.filter(line => line.trim()).map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            protocol: parts[0],
            state: parts[1],
            local: parts[3],
            remote: parts[4]
          };
        });
        resolve(connections);
      });
    });
  }

  async getDNSInfo() {
    return new Promise((resolve) => {
      const child = spawn('cat', ['/etc/resolv.conf']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const nameservers = output.split('\n')
          .filter(line => line.startsWith('nameserver'))
          .map(line => line.split(' ')[1]);
        resolve({ nameservers });
      });
    });
  }

  async getStorageInfo() {
    return {
      disks: await this.getDiskInfo(),
      filesystems: await this.getFilesystemInfo(),
      ioStats: await this.getIOStats()
    };
  }

  async getDiskInfo() {
    return new Promise((resolve) => {
      const child = spawn('lsblk', ['-d', '-o', 'NAME,SIZE,ROTA,TYPE,MOUNTPOINT']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n').slice(1);
        const disks = lines.filter(line => line.trim()).map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            name: parts[0],
            size: parts[1],
            rotational: parts[2] === '1',
            type: parts[3],
            mountpoint: parts[4] || null
          };
        });
        resolve(disks);
      });
    });
  }

  async getFilesystemInfo() {
    return new Promise((resolve) => {
      const child = spawn('df', ['-h']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n').slice(1);
        const filesystems = lines.filter(line => line.trim()).map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            filesystem: parts[0],
            size: parts[1],
            used: parts[2],
            available: parts[3],
            usage: parts[4],
            mountpoint: parts[5]
          };
        });
        resolve(filesystems);
      });
    });
  }

  async getIOStats() {
    return new Promise((resolve) => {
      const child = spawn('iostat', ['-x', '1', '1']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n');
        const deviceLine = lines.findIndex(line => line.includes('Device'));
        const dataLines = lines.slice(deviceLine + 2);

        const devices = dataLines.filter(line => line.trim()).map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            device: parts[0],
            rrqm_s: parseFloat(parts[1]),
            wrqm_s: parseFloat(parts[2]),
            r_s: parseFloat(parts[3]),
            w_s: parseFloat(parts[4]),
            rkB_s: parseFloat(parts[5]),
            wkB_s: parseFloat(parts[6]),
            await: parseFloat(parts[10]),
            util: parseFloat(parts[12])
          };
        });
        resolve(devices);
      });
    });
  }

  async getProcessInfo() {
    return new Promise((resolve) => {
      const child = spawn('ps', ['aux', '--sort=-%cpu', '--head=10']);
      let output = '';
      child.stdout.on('data', (data) => output += data.toString());
      child.on('close', () => {
        const lines = output.split('\n').slice(1);
        const processes = lines.filter(line => line.trim()).map(line => {
          const parts = line.trim().split(/\s+/);
          return {
            user: parts[0],
            pid: parts[1],
            cpu: parts[2],
            mem: parts[3],
            vsz: parts[4],
            rss: parts[5],
            tty: parts[6],
            stat: parts[7],
            start: parts[8],
            time: parts[9],
            command: parts.slice(10).join(' ')
          };
        });
        resolve(processes);
      });
    });
  }

  async performPerformanceProfiling() {
    console.log('⚡ Performing Performance Profiling...');

    const performanceProfile = {
      cpuBenchmark: await this.benchmarkCPU(),
      memoryBenchmark: await this.benchmarkMemory(),
      diskBenchmark: await this.benchmarkDisk(),
      networkBenchmark: await this.benchmarkNetwork(),
      systemLoad: await this.analyzeSystemLoad()
    };

    this.profileData.performanceProfile = performanceProfile;
    console.log('✅ Performance profiling completed');
  }

  async benchmarkCPU() {
    const iterations = 10000000;
    const start = performance.now();

    // CPU-intensive calculation
    let result = 0;
    for (let i = 0; i < iterations; i++) {
      result += Math.sqrt(i) * Math.sin(i) * Math.cos(i);
    }

    const time = performance.now() - start;

    return {
      operationsPerSecond: iterations / (time / 1000),
      totalTime: time,
      iterations: iterations,
      score: Math.round(1000000 / time) // Score based on time per million ops
    };
  }

  async benchmarkMemory() {
    const start = performance.now();
    const objects = [];

    // Memory allocation test
    for (let i = 0; i < 100000; i++) {
      objects.push({
        id: i,
        data: new Array(100).fill(Math.random()),
        timestamp: Date.now()
      });
    }

    const allocTime = performance.now() - start;

    // Memory access test
    const accessStart = performance.now();
    let sum = 0;
    for (const obj of objects) {
      sum += obj.data[0];
    }
    const accessTime = performance.now() - accessStart;

    // Cleanup
    objects.length = 0;

    return {
      allocationTime: allocTime,
      accessTime: accessTime,
      objectsCreated: 100000,
      allocationRate: 100000 / (allocTime / 1000),
      accessRate: 100000 / (accessTime / 1000)
    };
  }

  async benchmarkDisk() {
    const testFile = '/tmp/disk_benchmark_test.tmp';
    const testData = 'x'.repeat(1024 * 1024); // 1MB test data
    const iterations = 10;

    // Write test
    const writeStart = performance.now();
    for (let i = 0; i < iterations; i++) {
      await fs.promises.writeFile(testFile, testData + i);
    }
    const writeTime = performance.now() - writeStart;

    // Read test
    const readStart = performance.now();
    for (let i = 0; i < iterations; i++) {
      await fs.promises.readFile(testFile);
    }
    const readTime = performance.now() - readStart;

    // Cleanup
    await fs.promises.unlink(testFile);

    return {
      writeSpeed: (iterations * 1024 * 1024) / (writeTime / 1000), // MB/s
      readSpeed: (iterations * 1024 * 1024) / (readTime / 1000), // MB/s
      writeTime: writeTime,
      readTime: readTime,
      dataSize: iterations * 1024 * 1024 // bytes
    };
  }

  async benchmarkNetwork() {
    const start = performance.now();

    // Network connectivity test
    try {
      await this.pingTest('8.8.8.8');
      const pingTime = performance.now() - start;

      return {
        connectivity: 'OK',
        latency: pingTime,
        status: 'Connected'
      };
    } catch (error) {
      return {
        connectivity: 'Failed',
        latency: -1,
        status: 'Disconnected',
        error: error.message
      };
    }
  }

  async pingTest(host) {
    return new Promise((resolve, reject) => {
      const child = spawn('ping', ['-c', '1', '-W', '5', host]);
      child.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`Ping failed with code ${code}`));
      });
    });
  }

  async analyzeSystemLoad() {
    const loadAvg = os.loadavg();
    const cpuCount = os.cpus().length;

    return {
      load1m: loadAvg[0],
      load5m: loadAvg[1],
      load15m: loadAvg[2],
      cpuCount: cpuCount,
      loadPerCPU: {
        '1m': (loadAvg[0] / cpuCount).toFixed(2),
        '5m': (loadAvg[1] / cpuCount).toFixed(2),
        '15m': (loadAvg[2] / cpuCount).toFixed(2)
      },
      memoryUsage: {
        total: os.totalmem(),
        free: os.freemem(),
        used: os.totalmem() - os.freemem(),
        percentage: ((os.totalmem() - os.freemem()) / os.totalmem() * 100).toFixed(2)
      }
    };
  }

  async analyzeBottlenecks() {
    console.log('🔍 Analyzing System Bottlenecks...');

    const bottleneckAnalysis = {
      cpu: this.analyzeCPUBottlenecks(),
      memory: this.analyzeMemoryBottlenecks(),
      disk: this.analyzeDiskBottlenecks(),
      network: this.analyzeNetworkBottlenecks(),
      system: this.analyzeSystemBottlenecks()
    };

    this.profileData.bottleneckAnalysis = bottleneckAnalysis;
    console.log('✅ Bottleneck analysis completed');
  }

  analyzeCPUBottlenecks() {
    const load = this.profileData.performanceProfile.systemLoad;
    const cpuBenchmark = this.profileData.performanceProfile.cpuBenchmark;

    const bottlenecks = [];
    const recommendations = [];

    if (parseFloat(load.loadPerCPU['1m']) > 2.0) {
      bottlenecks.push('High CPU load per core');
      recommendations.push('Consider CPU-intensive process optimization');
    }

    if (cpuBenchmark.score < 500) {
      bottlenecks.push('Low CPU performance score');
      recommendations.push('CPU may be bottlenecked by thermal throttling or frequency scaling');
    }

    return {
      bottlenecks,
      recommendations,
      severity: bottlenecks.length > 0 ? 'HIGH' : 'LOW'
    };
  }

  analyzeMemoryBottlenecks() {
    const memUsage = this.profileData.performanceProfile.systemLoad.memoryUsage;
    const memBenchmark = this.profileData.performanceProfile.memoryBenchmark;

    const bottlenecks = [];
    const recommendations = [];

    if (parseFloat(memUsage.percentage) > 85) {
      bottlenecks.push('High memory usage');
      recommendations.push('Consider memory optimization or adding more RAM');
    }

    if (memBenchmark.allocationRate < 1000000) {
      bottlenecks.push('Slow memory allocation');
      recommendations.push('Memory allocation patterns may need optimization');
    }

    return {
      bottlenecks,
      recommendations,
      severity: bottlenecks.length > 0 ? 'HIGH' : 'LOW'
    };
  }

  analyzeDiskBottlenecks() {
    const diskBenchmark = this.profileData.performanceProfile.diskBenchmark;
    const ioStats = this.profileData.systemInfo.storage.ioStats;

    const bottlenecks = [];
    const recommendations = [];

    if (diskBenchmark.writeSpeed < 100) {
      bottlenecks.push('Slow disk write speed');
      recommendations.push('Consider SSD upgrade or disk optimization');
    }

    if (ioStats.length > 0) {
      const maxUtil = Math.max(...ioStats.map(d => d.util));
      if (maxUtil > 80) {
        bottlenecks.push('High disk utilization');
        recommendations.push('Disk I/O is a potential bottleneck');
      }
    }

    return {
      bottlenecks,
      recommendations,
      severity: bottlenecks.length > 0 ? 'MEDIUM' : 'LOW'
    };
  }

  analyzeNetworkBottlenecks() {
    const networkBenchmark = this.profileData.performanceProfile.networkBenchmark;

    const bottlenecks = [];
    const recommendations = [];

    if (networkBenchmark.connectivity !== 'OK') {
      bottlenecks.push('Network connectivity issues');
      recommendations.push('Check network configuration and connectivity');
    } else if (networkBenchmark.latency > 100) {
      bottlenecks.push('High network latency');
      recommendations.push('Consider network optimization');
    }

    return {
      bottlenecks,
      recommendations,
      severity: bottlenecks.length > 0 ? 'MEDIUM' : 'LOW'
    };
  }

  analyzeSystemBottlenecks() {
    const allBottlenecks = [
      ...this.profileData.bottleneckAnalysis.cpu.bottlenecks,
      ...this.profileData.bottleneckAnalysis.memory.bottlenecks,
      ...this.profileData.bottleneckAnalysis.disk.bottlenecks,
      ...this.profileData.bottleneckAnalysis.network.bottlenecks
    ];

    return {
      totalBottlenecks: allBottlenecks.length,
      criticalBottlenecks: allBottlenecks.length > 3,
      overallHealth: allBottlenecks.length === 0 ? 'EXCELLENT' :
                     allBottlenecks.length <= 2 ? 'GOOD' :
                     allBottlenecks.length <= 4 ? 'FAIR' : 'POOR'
    };
  }

  async performSystemHealthCheck() {
    console.log('🏥 Performing System Health Check...');

    const healthCheck = {
      overall: 'UNKNOWN',
      components: {
        cpu: await this.checkCPUHealth(),
        memory: await this.checkMemoryHealth(),
        disk: await this.checkDiskHealth(),
        network: await this.checkNetworkHealth()
      },
      alerts: []
    };

    // Determine overall health
    const componentHealths = Object.values(healthCheck.components);
    const criticalCount = componentHealths.filter(h => h.status === 'CRITICAL').length;
    const warningCount = componentHealths.filter(h => h.status === 'WARNING').length;

    if (criticalCount > 0) {
      healthCheck.overall = 'CRITICAL';
    } else if (warningCount > 2) {
      healthCheck.overall = 'WARNING';
    } else if (warningCount > 0) {
      healthCheck.overall = 'GOOD';
    } else {
      healthCheck.overall = 'EXCELLENT';
    }

    this.profileData.healthCheck = healthCheck;
    console.log(`✅ System health check completed: ${healthCheck.overall}`);
  }

  async checkCPUHealth() {
    const load = this.profileData.performanceProfile.systemLoad;
    const loadPerCPU = parseFloat(load.loadPerCPU['1m']);

    let status = 'OK';
    const alerts = [];

    if (loadPerCPU > 4.0) {
      status = 'CRITICAL';
      alerts.push('CPU severely overloaded');
    } else if (loadPerCPU > 2.0) {
      status = 'WARNING';
      alerts.push('CPU heavily loaded');
    }

    return { status, alerts };
  }

  async checkMemoryHealth() {
    const memUsage = this.profileData.performanceProfile.systemLoad.memoryUsage;
    const usagePercent = parseFloat(memUsage.percentage);

    let status = 'OK';
    const alerts = [];

    if (usagePercent > 90) {
      status = 'CRITICAL';
      alerts.push('Memory critically low');
    } else if (usagePercent > 80) {
      status = 'WARNING';
      alerts.push('Memory usage high');
    }

    return { status, alerts };
  }

  async checkDiskHealth() {
    const filesystems = this.profileData.systemInfo.storage.filesystems;

    let status = 'OK';
    const alerts = [];

    for (const fs of filesystems) {
      const usage = parseInt(fs.usage);
      if (usage > 95) {
        status = 'CRITICAL';
        alerts.push(`Disk ${fs.filesystem} critically full`);
      } else if (usage > 85) {
        if (status !== 'CRITICAL') status = 'WARNING';
        alerts.push(`Disk ${fs.filesystem} usage high`);
      }
    }

    return { status, alerts };
  }

  async checkNetworkHealth() {
    const networkBenchmark = this.profileData.performanceProfile.networkBenchmark;

    let status = 'OK';
    const alerts = [];

    if (networkBenchmark.connectivity !== 'OK') {
      status = 'CRITICAL';
      alerts.push('Network connectivity lost');
    } else if (networkBenchmark.latency > 200) {
      status = 'WARNING';
      alerts.push('High network latency');
    }

    return { status, alerts };
  }

  async generateOptimizationSuggestions() {
    console.log('💡 Generating Optimization Suggestions...');

    const suggestions = {
      immediate: [],
      shortTerm: [],
      longTerm: [],
      monitoring: []
    };

    // CPU optimizations
    const cpuBottlenecks = this.profileData.bottleneckAnalysis.cpu;
    if (cpuBottlenecks.severity === 'HIGH') {
      suggestions.immediate.push('Reduce CPU-intensive processes');
      suggestions.shortTerm.push('Optimize algorithms and code efficiency');
      suggestions.longTerm.push('Consider CPU upgrade or additional cores');
    }

    // Memory optimizations
    const memBottlenecks = this.profileData.bottleneckAnalysis.memory;
    if (memBottlenecks.severity === 'HIGH') {
      suggestions.immediate.push('Clear memory caches and restart memory-intensive applications');
      suggestions.shortTerm.push('Implement memory pooling and optimize data structures');
      suggestions.longTerm.push('Add more RAM or upgrade to faster memory');
    }

    // Disk optimizations
    const diskBottlenecks = this.profileData.bottleneckAnalysis.disk;
    if (diskBottlenecks.severity === 'HIGH') {
      suggestions.immediate.push('Clean up temporary files and clear disk space');
      suggestions.shortTerm.push('Optimize disk I/O patterns and implement caching');
      suggestions.longTerm.push('Upgrade to SSD or faster storage solution');
    }

    // General monitoring suggestions
    suggestions.monitoring.push('Implement continuous system monitoring');
    suggestions.monitoring.push('Set up automated alerts for resource thresholds');
    suggestions.monitoring.push('Regular performance profiling and analysis');

    this.profileData.optimizationSuggestions = suggestions;
    console.log('✅ Optimization suggestions generated');
  }

  async createProfileReport() {
    console.log('📋 Creating System Profile Report...');

    const reportPath = '/workspaces/ai-kubernetes-api-generator-demo/docs/SYSTEM_PROFILE_REPORT.md';

    const report = `# Comprehensive System Profile Report

Generated: ${new Date().toISOString()}

## Executive Summary

**Overall System Health:** ${this.profileData.healthCheck.overall}
**Total Bottlenecks Identified:** ${this.profileData.bottleneckAnalysis.system.totalBottlenecks}
**Critical Issues:** ${this.profileData.bottleneckAnalysis.system.criticalBottlenecks ? 'Yes' : 'No'}

## System Specifications

### Hardware Information
- **CPU:** ${this.profileData.systemInfo.hardware.cpu.model}
- **Cores:** ${this.profileData.systemInfo.hardware.cpu.cores}
- **Architecture:** ${this.profileData.systemInfo.hardware.cpu.architecture}
- **Total Memory:** ${Math.round(this.profileData.systemInfo.hardware.memory.total / 1024 / 1024 / 1024)}GB
- **Available Memory:** ${Math.round(this.profileData.systemInfo.hardware.memory.available / 1024 / 1024 / 1024)}GB

### Software Information
- **Operating System:** ${this.profileData.systemInfo.software.os.description}
- **Kernel Version:** ${this.profileData.systemInfo.software.os.kernel}
- **Node.js Version:** ${this.profileData.systemInfo.software.node.version}
- **System Uptime:** ${Math.round(this.profileData.systemInfo.software.runtime.uptime / 3600)} hours

## Performance Benchmarks

### CPU Performance
- **Operations/Second:** ${Math.round(this.profileData.performanceProfile.cpuBenchmark.operationsPerSecond)}
- **Benchmark Score:** ${this.profileData.performanceProfile.cpuBenchmark.score}
- **Performance Rating:** ${this.getCPUPerformanceRating()}

### Memory Performance
- **Allocation Rate:** ${Math.round(this.profileData.performanceProfile.memoryBenchmark.allocationRate)} objects/sec
- **Access Rate:** ${Math.round(this.profileData.performanceProfile.memoryBenchmark.accessRate)} objects/sec
- **Memory Efficiency:** ${this.getMemoryEfficiencyRating()}

### Disk Performance
- **Write Speed:** ${this.profileData.performanceProfile.diskBenchmark.writeSpeed.toFixed(2)} MB/s
- **Read Speed:** ${this.profileData.performanceProfile.diskBenchmark.readSpeed.toFixed(2)} MB/s
- **Disk Rating:** ${this.getDiskPerformanceRating()}

### Network Performance
- **Connectivity:** ${this.profileData.performanceProfile.networkBenchmark.status}
- **Latency:** ${this.profileData.performanceProfile.networkBenchmark.latency.toFixed(2)}ms

## System Load Analysis

- **1-minute Load Average:** ${this.profileData.performanceProfile.systemLoad.load1m}
- **Load per CPU Core:** ${this.profileData.performanceProfile.systemLoad.loadPerCPU['1m']}
- **Memory Usage:** ${this.profileData.performanceProfile.systemLoad.memoryUsage.percentage}%
- **Load Assessment:** ${this.getLoadAssessment()}

## Bottleneck Analysis

### CPU Bottlenecks
${this.profileData.bottleneckAnalysis.cpu.bottlenecks.length > 0 ?
  this.profileData.bottleneckAnalysis.cpu.bottlenecks.map(b => `- ${b}`).join('\n') :
  '✅ No significant CPU bottlenecks identified'}

### Memory Bottlenecks
${this.profileData.bottleneckAnalysis.memory.bottlenecks.length > 0 ?
  this.profileData.bottleneckAnalysis.memory.bottlenecks.map(b => `- ${b}`).join('\n') :
  '✅ No significant memory bottlenecks identified'}

### Disk Bottlenecks
${this.profileData.bottleneckAnalysis.disk.bottlenecks.length > 0 ?
  this.profileData.bottleneckAnalysis.disk.bottlenecks.map(b => `- ${b}`).join('\n') :
  '✅ No significant disk bottlenecks identified'}

### Network Bottlenecks
${this.profileData.bottleneckAnalysis.network.bottlenecks.length > 0 ?
  this.profileData.bottleneckAnalysis.network.bottlenecks.map(b => `- ${b}`).join('\n') :
  '✅ No significant network bottlenecks identified'}

## System Health Check

### Component Health Status
- **CPU:** ${this.profileData.healthCheck.components.cpu.status}
- **Memory:** ${this.profileData.healthCheck.components.memory.status}
- **Disk:** ${this.profileData.healthCheck.components.disk.status}
- **Network:** ${this.profileData.healthCheck.components.network.status}

### Active Alerts
${this.getAllAlerts().length > 0 ?
  this.getAllAlerts().map(alert => `- ⚠️ ${alert}`).join('\n') :
  '✅ No active system alerts'}

## Optimization Recommendations

### Immediate Actions (Next 24 Hours)
${this.profileData.optimizationSuggestions.immediate.length > 0 ?
  this.profileData.optimizationSuggestions.immediate.map(rec => `- ${rec}`).join('\n') :
  'No immediate actions required'}

### Short-term Improvements (Next Week)
${this.profileData.optimizationSuggestions.shortTerm.length > 0 ?
  this.profileData.optimizationSuggestions.shortTerm.map(rec => `- ${rec}`).join('\n') :
  'No short-term improvements required'}

### Long-term Strategy (Next Month)
${this.profileData.optimizationSuggestions.longTerm.length > 0 ?
  this.profileData.optimizationSuggestions.longTerm.map(rec => `- ${rec}`).join('\n') :
  'No long-term strategy changes required'}

### Monitoring Recommendations
${this.profileData.optimizationSuggestions.monitoring.map(rec => `- ${rec}`).join('\n')}

## Performance Insights

### System Strengths
${this.identifySystemStrengths()}

### Areas for Improvement
${this.identifyImprovementAreas()}

### Capacity Planning
${this.generateCapacityPlanningAdvice()}

## Technical Details

### Network Interfaces
${Object.entries(this.profileData.systemInfo.network.interfaces).map(([name, addrs]) =>
`- **${name}:** ${addrs.map(a => `${a.address} (${a.family})`).join(', ')}`
).join('\n')}

### File Systems
${this.profileData.systemInfo.storage.filesystems.map(fs =>
`- **${fs.filesystem}** (${fs.size}): ${fs.used} used, ${fs.available} available (${fs.usage})`
).join('\n')}

### Top Processes by CPU Usage
${this.profileData.systemInfo.processes.slice(0, 5).map(proc =>
`- **${proc.command}** (PID: ${proc.pid}): ${proc.cpu}% CPU, ${proc.mem}% MEM`
).join('\n')}

---

*Report generated by Advanced System Profiler*
*All measurements are based on current system conditions and may vary under different workloads*
`;

    await fs.promises.writeFile(reportPath, report);

    // Also save raw profile data
    const jsonPath = reportPath.replace('.md', '.json');
    await fs.promises.writeFile(jsonPath, JSON.stringify(this.profileData, null, 2));

    console.log(`📋 System profile report saved: ${reportPath}`);
    console.log(`📊 Raw profile data saved: ${jsonPath}`);
  }

  // Helper methods for generating ratings and assessments
  getCPUPerformanceRating() {
    const score = this.profileData.performanceProfile.cpuBenchmark.score;
    if (score > 1000) return 'Excellent';
    if (score > 700) return 'Good';
    if (score > 500) return 'Fair';
    return 'Poor';
  }

  getMemoryEfficiencyRating() {
    const allocRate = this.profileData.performanceProfile.memoryBenchmark.allocationRate;
    if (allocRate > 2000000) return 'Excellent';
    if (allocRate > 1000000) return 'Good';
    if (allocRate > 500000) return 'Fair';
    return 'Poor';
  }

  getDiskPerformanceRating() {
    const writeSpeed = this.profileData.performanceProfile.diskBenchmark.writeSpeed;
    if (writeSpeed > 500) return 'Excellent';
    if (writeSpeed > 200) return 'Good';
    if (writeSpeed > 100) return 'Fair';
    return 'Poor';
  }

  getLoadAssessment() {
    const loadPerCPU = parseFloat(this.profileData.performanceProfile.systemLoad.loadPerCPU['1m']);
    if (loadPerCPU < 1.0) return 'Light Load';
    if (loadPerCPU < 2.0) return 'Moderate Load';
    if (loadPerCPU < 4.0) return 'Heavy Load';
    return 'Overloaded';
  }

  getAllAlerts() {
    const alerts = [];
    Object.values(this.profileData.healthCheck.components).forEach(component => {
      alerts.push(...component.alerts);
    });
    return alerts;
  }

  identifySystemStrengths() {
    const strengths = [];

    if (this.profileData.healthCheck.overall === 'EXCELLENT' || this.profileData.healthCheck.overall === 'GOOD') {
      strengths.push('System shows healthy overall performance');
    }

    if (this.profileData.performanceProfile.cpuBenchmark.score > 700) {
      strengths.push('Strong CPU performance capabilities');
    }

    if (parseFloat(this.profileData.performanceProfile.systemLoad.memoryUsage.percentage) < 70) {
      strengths.push('Adequate memory availability');
    }

    if (this.profileData.performanceProfile.diskBenchmark.writeSpeed > 200) {
      strengths.push('Good disk I/O performance');
    }

    return strengths.length > 0 ? strengths.map(s => `- ${s}`).join('\n') : '- No specific strengths identified';
  }

  identifyImprovementAreas() {
    const areas = [];

    if (this.profileData.bottleneckAnalysis.cpu.severity === 'HIGH') {
      areas.push('CPU optimization could improve overall performance');
    }

    if (this.profileData.bottleneckAnalysis.memory.severity === 'HIGH') {
      areas.push('Memory management optimization needed');
    }

    if (this.profileData.bottleneckAnalysis.disk.severity === 'HIGH') {
      areas.push('Disk performance improvements would be beneficial');
    }

    return areas.length > 0 ? areas.map(a => `- ${a}`).join('\n') : '- No immediate improvement areas identified';
  }

  generateCapacityPlanningAdvice() {
    const advice = [];

    const memUsage = parseFloat(this.profileData.performanceProfile.systemLoad.memoryUsage.percentage);
    if (memUsage > 70) {
      advice.push('Consider memory upgrade in next 3-6 months');
    }

    const loadPerCPU = parseFloat(this.profileData.performanceProfile.systemLoad.loadPerCPU['1m']);
    if (loadPerCPU > 1.5) {
      advice.push('Monitor CPU utilization and plan for upgrade if trend continues');
    }

    advice.push('Regular monitoring to identify capacity trends');
    advice.push('Plan for 20-30% headroom for peak loads');

    return advice.map(a => `- ${a}`).join('\n');
  }
}

// Command line interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const profiler = new SystemProfiler();

  console.log('🔬 Starting Comprehensive System Profiling');

  profiler.runComprehensiveProfile()
    .then(() => {
      console.log('\n🎉 System Profiling Completed!');
      process.exit(0);
    })
    .catch((error) => {
      console.error('\n❌ System profiling failed:', error);
      process.exit(1);
    });
}

export default SystemProfiler;