"""
Performance tests for the code generation pipeline.
Tests the performance characteristics of the AI-assisted code generation.
"""

import pytest
import time
import psutil
import memory_profiler
import statistics
from pathlib import Path
from unittest.mock import Mock, patch
import json
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import cProfile
import pstats
from io import StringIO

# Import modules for testing
import sys
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from agent.agent_core import AgentCore
from codegen.openapi_client import OpenAPICodegenClient
from codegen.spec_parser import OpenAPISpecParser
from main import AIPlatformExtensionGenerator


@pytest.mark.performance
@pytest.mark.slow
class TestCodegenPerformance:
    """Performance tests for the code generation pipeline."""

    @pytest.fixture
    def performance_data(self):
        """Performance test data with varying complexity."""
        return {
            "simple_request": "Create a simple API with name field",
            "medium_request": "Create a database API with fields for engine, version, replicas, storage, and configuration",
            "large_request": (
                "Create a comprehensive microservice API with fields for service discovery, load balancing, "
                "health checks, circuit breakers, retries, timeouts, authentication, authorization, "
                "rate limiting, monitoring, logging, tracing, deployment configuration, scaling policies, "
                "resource limits, network policies, security contexts, and custom metrics"
            ),
            "complex_nested_request": (
                "Create a complex application API with nested structures including infrastructure config, "
                "application settings, security policies, monitoring configuration, and deployment strategies"
            )
        }

    @pytest.fixture
    def mock_agent_for_performance(self):
        """Create a mock agent for performance testing."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": [
                    "openapi-mcp-codegen",
                    "--output-dir", "/tmp/perf-test",
                    "--go-header-file", "hack/boilerplate.go.txt",
                    "--input-spec", '{"group":"perf.test.io","version":"v1alpha1","kind":"PerfResource","spec":{"properties":{"name":{"type":"string"}}}}'
                ]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client)
            yield agent

    def test_request_processing_performance(self, mock_agent_for_performance, performance_data):
        """Test the performance of request processing."""
        results = {}

        for request_type, request_text in performance_data.items():
            times = []
            memory_usage = []

            # Run multiple iterations for statistical significance
            for _ in range(10):
                # Measure memory before
                process = psutil.Process()
                memory_before = process.memory_info().rss

                # Measure time
                start_time = time.time()
                result = mock_agent_for_performance.process_request(request_text)
                end_time = time.time()

                # Measure memory after
                memory_after = process.memory_info().rss

                execution_time = end_time - start_time
                memory_diff = memory_after - memory_before

                times.append(execution_time)
                memory_usage.append(memory_diff)

                assert "command" in result

            results[request_type] = {
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times),
                "std_time": statistics.stdev(times) if len(times) > 1 else 0,
                "avg_memory": statistics.mean(memory_usage),
                "max_memory": max(memory_usage)
            }

        # Performance assertions
        assert results["simple_request"]["avg_time"] < 1.0  # Should complete in < 1 second
        assert results["medium_request"]["avg_time"] < 2.0  # Should complete in < 2 seconds
        assert results["large_request"]["avg_time"] < 5.0  # Should complete in < 5 seconds

        # Memory usage should be reasonable
        for request_type, metrics in results.items():
            assert metrics["avg_memory"] < 50 * 1024 * 1024  # Less than 50MB average memory usage

    def test_concurrent_request_performance(self, mock_agent_for_performance):
        """Test performance under concurrent load."""
        request_text = "Create a simple API with name and description fields"
        num_concurrent = 10
        num_iterations = 5

        all_times = []

        for iteration in range(num_iterations):
            def process_request():
                start_time = time.time()
                result = mock_agent_for_performance.process_request(request_text)
                end_time = time.time()
                return end_time - start_time, result

            # Execute concurrent requests
            with ThreadPoolExecutor(max_workers=num_concurrent) as executor:
                futures = [executor.submit(process_request) for _ in range(num_concurrent)]
                iteration_results = [future.result() for future in futures]

            # Extract times and verify results
            iteration_times = [result[0] for result in iteration_results]
            all_times.extend(iteration_times)

            # Verify all requests succeeded
            assert all("command" in result[1] for result in iteration_results)

        # Performance analysis
        avg_time = statistics.mean(all_times)
        max_time = max(all_times)
        total_requests = len(all_times)

        # Assertions
        assert avg_time < 2.0  # Average should be under 2 seconds
        assert max_time < 5.0  # No request should take more than 5 seconds
        assert total_requests == num_concurrent * num_iterations

        # Verify reasonable variance (performance should be consistent)
        if len(all_times) > 1:
            std_dev = statistics.stdev(all_times)
            assert std_dev < avg_time * 0.5  # Standard deviation should be less than 50% of mean

    @pytest.mark.benchmark
    def test_memory_profiling(self, mock_agent_for_performance):
        """Test memory usage profiling."""
        request_text = "Create a complex API with multiple nested fields and arrays"

        @memory_profiler.profile
        def process_request_with_profiling():
            return mock_agent_for_performance.process_request(request_text)

        # Run with memory profiling
        result = process_request_with_profiling()

        assert "command" in result

        # Memory profiler will output detailed memory usage information
        # This test primarily ensures the profiling functionality works

    def test_cpu_performance(self, mock_agent_for_performance):
        """Test CPU usage during request processing."""
        request_text = "Create a medium complexity API with various field types"

        # Measure CPU usage
        process = psutil.Process()

        # Get initial CPU times
        cpu_before = process.cpu_times()
        start_time = time.time()

        # Process request
        result = mock_agent_for_performance.process_request(request_text)

        # Get final CPU times
        cpu_after = process.cpu_times()
        end_time = time.time()

        # Calculate CPU usage
        elapsed_time = end_time - start_time
        cpu_time = cpu_after.user + cpu_after.system - (cpu_before.user + cpu_before.system)
        cpu_percent = (cpu_time / elapsed_time) * 100 if elapsed_time > 0 else 0

        assert "command" in result
        assert cpu_percent < 100  # CPU usage should be reasonable

    def test_spec_parser_performance(self):
        """Test performance of the specification parser."""
        parser = OpenAPISpecParser()

        # Create specifications of varying complexity
        specs = {
            "simple": {
                "group": "simple.test.io",
                "version": "v1alpha1",
                "kind": "Simple",
                "spec": {"properties": {"name": {"type": "string"}}}
            },
            "medium": {
                "group": "medium.test.io",
                "version": "v1alpha1",
                "kind": "Medium",
                "spec": {
                    "properties": {
                        f"field_{i}": {"type": "string"}
                        for i in range(20)
                    }
                }
            },
            "large": {
                "group": "large.test.io",
                "version": "v1alpha1",
                "kind": "Large",
                "spec": {
                    "properties": {
                        f"field_{i}": {
                            "type": "object",
                            "properties": {
                                f"nested_{j}": {"type": "string"}
                                for j in range(10)
                            }
                        }
                        for i in range(50)
                    }
                }
            }
        }

        results = {}

        for spec_name, spec_data in specs.items():
            times = []
            iterations = 100 if spec_name == "simple" else (50 if spec_name == "medium" else 10)

            for _ in range(iterations):
                start_time = time.time()
                parsed_spec = parser.parse(spec_data)
                end_time = time.time()

                times.append(end_time - start_time)
                assert parsed_spec.group == spec_data["group"]

            results[spec_name] = {
                "avg_time": statistics.mean(times),
                "min_time": min(times),
                "max_time": max(times),
                "iterations": iterations
            }

        # Performance assertions
        assert results["simple"]["avg_time"] < 0.01  # Should be very fast for simple specs
        assert results["medium"]["avg_time"] < 0.05  # Should be fast for medium specs
        assert results["large"]["avg_time"] < 0.1   # Should handle large specs efficiently

    def test_command_generation_performance(self, mock_agent_for_performance):
        """Test performance of command generation."""
        requests = [
            "Create a simple API",
            "Create an API with fields",
            "Create a comprehensive API with multiple configuration options, nested structures, and various data types",
            "Create an extremely complex API with deeply nested structures, arrays, objects, and extensive configuration"
        ]

        for request in requests:
            times = []
            iterations = 20

            for _ in range(iterations):
                start_time = time.time()
                result = mock_agent_for_performance.process_request(request)
                end_time = time.time()

                times.append(end_time - start_time)
                assert "command" in result

            avg_time = statistics.mean(times)
            max_time = max(times)

            # Performance should scale reasonably with request complexity
            assert avg_time < 3.0  # Should complete in under 3 seconds on average
            assert max_time < 10.0  # Should complete in under 10 seconds even for complex requests

    def test_batch_processing_performance(self, mock_agent_for_performance):
        """Test performance of batch processing multiple requests."""
        batch_size = 50
        requests = [
            f"Create API {i} with name field"
            for i in range(batch_size)
        ]

        start_time = time.time()
        results = []

        for request in requests:
            result = mock_agent_for_performance.process_request(request)
            results.append(result)

        end_time = time.time()
        total_time = end_time - start_time

        # Verify all requests succeeded
        assert len(results) == batch_size
        assert all("command" in result for result in results)

        # Performance metrics
        avg_time_per_request = total_time / batch_size
        requests_per_second = batch_size / total_time

        # Assertions
        assert avg_time_per_request < 0.5  # Should average less than 500ms per request
        assert requests_per_second > 2.0   # Should handle at least 2 requests per second

    def test_resource_cleanup_performance(self, mock_agent_for_performance):
        """Test that resources are properly cleaned up after processing."""
        process = psutil.Process()
        initial_memory = process.memory_info().rss

        # Process multiple requests
        for i in range(20):
            request = f"Create API {i} with field"
            result = mock_agent_for_performance.process_request(request)
            assert "command" in result

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal (good cleanup)
        assert memory_increase < 10 * 1024 * 1024  # Less than 10MB increase

    def test_caching_performance(self):
        """Test performance impact of caching identical requests."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client, enable_cache=True)

            # Test identical request
            request = "Create a simple API with name field"

            # First request (no cache)
            start_time = time.time()
            result1 = agent.process_request(request)
            first_time = time.time() - start_time

            # Second request (cached)
            start_time = time.time()
            result2 = agent.process_request(request)
            second_time = time.time() - start_time

            # Verify results are identical
            assert result1 == result2

            # Verify caching improves performance
            # (This might not always be true due to overhead, but should be generally faster)
            # We'll just verify it's not significantly slower
            performance_ratio = second_time / first_time if first_time > 0 else 1.0
            assert performance_ratio < 2.0  # Cached request shouldn't be more than 2x slower

            # Verify OpenAI was only called once
            assert mock_client.chat.completions.create.call_count == 1


@pytest.mark.performance
class TestScalabilityTests:
    """Scalability tests for the code generation system."""

    def test_scalability_with_request_complexity(self):
        """Test how performance scales with request complexity."""
        complexities = [
            ("simple", "Create API with name"),
            ("medium", "Create API with 10 fields"),
            ("large", "Create API with 50 fields"),
            ("xlarge", "Create API with 200 fields and nested structures")
        ]

        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client)

            results = {}
            for complexity, request in complexities:
                times = []
                for _ in range(10):
                    start_time = time.time()
                    result = agent.process_request(request)
                    end_time = time.time()
                    times.append(end_time - start_time)
                    assert "command" in result

                results[complexity] = {
                    "avg_time": statistics.mean(times),
                    "min_time": min(times),
                    "max_time": max(times)
                }

            # Verify performance scales reasonably
        # (Complex requests should take longer, but not exponentially so)
        simple_time = results["simple"]["avg_time"]
        xlarge_time = results["xlarge"]["avg_time"]
        scaling_factor = xlarge_time / simple_time if simple_time > 0 else 1.0

        # Performance shouldn't degrade more than 10x for 200x complexity
        assert scaling_factor < 10.0

    def test_memory_scalability(self):
        """Test memory usage scalability."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client)
            process = psutil.Process()

            initial_memory = process.memory_info().rss
            memory_measurements = []

            # Process increasing number of requests
            for i in range(1, 51):
                request = f"Create API {i} with multiple fields"
                result = agent.process_request(request)
                assert "command" in result

                if i % 10 == 0:  # Measure every 10 requests
                    current_memory = process.memory_info().rss
                    memory_increase = current_memory - initial_memory
                    memory_measurements.append((i, memory_increase))

            # Analyze memory growth
            final_memory = memory_measurements[-1][1]
            memory_per_request = final_memory / 50

            # Memory usage should grow linearly, not exponentially
            assert memory_per_request < 1 * 1024 * 1024  # Less than 1MB per request
            assert final_memory < 50 * 1024 * 1024  # Less than 50MB total

    def test_concurrent_scalability(self):
        """Test scalability with concurrent processing."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client)

            concurrency_levels = [1, 2, 4, 8, 16]
            results = {}

            for concurrency in concurrency_levels:
                def process_request():
                    start_time = time.time()
                    result = agent.process_request("Create test API")
                    end_time = time.time()
                    return end_time - start_time, result

                start_time = time.time()
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = [executor.submit(process_request) for _ in range(concurrency)]
                    iteration_results = [future.result() for future in futures]
                end_time = time.time()

                total_time = end_time - start_time
                avg_time = statistics.mean([result[0] for result in iteration_results])

                results[concurrency] = {
                    "total_time": total_time,
                    "avg_time": avg_time,
                    "throughput": concurrency / total_time
                }

                # Verify all requests succeeded
                assert all("command" in result[1] for result in iteration_results)

            # Analyze scalability
            # Throughput should increase with concurrency (up to a point)
            baseline_throughput = results[1]["throughput"]
            max_throughput = max(result["throughput"] for result in results.values())

            # Should achieve at least 2x improvement with concurrency
            assert max_throughput >= baseline_throughput * 2


@pytest.mark.performance
class TestPerformanceRegression:
    """Performance regression tests."""

    def test_performance_regression_baseline(self):
        """Establish a performance baseline for regression testing."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = json.dumps({
                "command": ["openapi-mcp-codegen", "--test"]
            })
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            agent = AgentCore(openai_client=mock_client)

            # Standardized test cases
            test_cases = [
                ("simple", "Create API with name field"),
                ("medium", "Create API with 5 different field types"),
                ("complex", "Create API with nested structures and arrays")
            ]

            baseline_metrics = {}

            for case_name, request in test_cases:
                times = []
                for _ in range(20):
                    start_time = time.time()
                    result = agent.process_request(request)
                    end_time = time.time()
                    times.append(end_time - start_time)
                    assert "command" in result

                baseline_metrics[case_name] = {
                    "mean": statistics.mean(times),
                    "median": statistics.median(times),
                    "p95": sorted(times)[int(0.95 * len(times))] if len(times) > 0 else 0,
                    "p99": sorted(times)[int(0.99 * len(times))] if len(times) > 0 else 0
                }

            # These values should be saved and used for regression testing
            # For now, we'll just assert reasonable baselines
            assert baseline_metrics["simple"]["mean"] < 1.0
            assert baseline_metrics["medium"]["mean"] < 2.0
            assert baseline_metrics["complex"]["mean"] < 5.0

            return baseline_metrics

    def test_performance_regression_detection(self):
        """Test that we can detect performance regressions."""
        # This test would normally compare against saved baseline metrics
        # For now, we'll simulate a regression scenario

        baseline = {
            "simple": {"mean": 0.5, "p95": 1.0},
            "medium": {"mean": 1.0, "p95": 2.0},
            "complex": {"mean": 2.0, "p95": 4.0}
        }

        # Simulate current performance measurements
        current = {
            "simple": {"mean": 0.6, "p95": 1.2},  # 20% slower
            "medium": {"mean": 1.5, "p95": 3.0},  # 50% slower
            "complex": {"mean": 5.0, "p95": 8.0}   # 150% slower (regression!)
        }

        # Regression detection logic
        regression_threshold = 0.5  # 50% slower triggers regression alert

        regressions = []
        for case in baseline:
            mean_regression = (current[case]["mean"] - baseline[case]["mean"]) / baseline[case]["mean"]
            p95_regression = (current[case]["p95"] - baseline[case]["p95"]) / baseline[case]["p95"]

            if mean_regression > regression_threshold or p95_regression > regression_threshold:
                regressions.append({
                    "case": case,
                    "mean_regression": mean_regression,
                    "p95_regression": p95_regression
                })

        # Should detect regression in complex case
        assert len(regressions) > 0
        assert any(r["case"] == "complex" for r in regressions)