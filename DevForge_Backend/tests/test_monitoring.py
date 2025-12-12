"""Tests for monitoring endpoints.

Tests health checks, metrics API, cache stats, and configuration endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from datetime import datetime

from src.main import app
from src.core.performance import PerformanceMetrics, SimpleCache


client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint"""
    
    def test_health_check(self):
        """Test /monitoring/health endpoint"""
        response = client.get("/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.8.0"
    
    def test_health_includes_timestamp(self):
        """Test health check includes valid timestamp"""
        response = client.get("/monitoring/health")
        data = response.json()
        
        # Verify timestamp is valid ISO format
        timestamp = datetime.fromisoformat(data["timestamp"])
        assert timestamp is not None


class TestMetricsEndpoints:
    """Test metrics endpoints"""
    
    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test GET /monitoring/metrics"""
        # Setup test metrics
        metrics = PerformanceMetrics()
        await metrics.record("test_metric", 100.0)
        await metrics.record("test_metric", 200.0)
        
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            response = client.get("/monitoring/metrics")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "timestamp" in data
            assert "metrics" in data
            assert "test_metric" in data["metrics"]
    
    @pytest.mark.asyncio
    async def test_get_specific_metric(self):
        """Test GET /monitoring/metrics/{metric_name}"""
        metrics = PerformanceMetrics()
        await metrics.record("github_api_call", 150.5)
        
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            response = client.get("/monitoring/metrics/github_api_call")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["metric"] == "github_api_call"
            assert "stats" in data
            assert data["stats"]["count"] == 1
    
    @pytest.mark.asyncio
    async def test_nonexistent_metric(self):
        """Test requesting nonexistent metric"""
        metrics = PerformanceMetrics()
        
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            response = client.get("/monitoring/metrics/nonexistent")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "error" in data
            assert "available_metrics" in data


class TestCacheEndpoints:
    """Test cache management endpoints"""
    
    @pytest.mark.asyncio
    async def test_cache_stats(self):
        """Test GET /monitoring/cache/stats"""
        cache = SimpleCache()
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        
        with patch('src.api.monitoring.get_cache', return_value=cache):
            response = client.get("/monitoring/cache/stats")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "total_entries" in data
            assert "cache_enabled" in data
            assert data["cache_enabled"] is True
    
    @pytest.mark.asyncio
    async def test_cache_clear(self):
        """Test POST /monitoring/cache/clear"""
        cache = SimpleCache()
        await cache.set("key1", "value1")
        
        with patch('src.api.monitoring.get_cache', return_value=cache):
            response = client.post("/monitoring/cache/clear")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert "message" in data
            
            # Verify cache was actually cleared
            assert len(cache._cache) == 0


class TestPerformanceSummary:
    """Test performance summary endpoint"""
    
    @pytest.mark.asyncio
    async def test_performance_summary(self):
        """Test GET /monitoring/performance/summary"""
        metrics = PerformanceMetrics()
        await metrics.record("repo_discovery", 150.0)
        await metrics.record("llm_call", 2000.0)
        
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            response = client.get("/monitoring/performance/summary")
            
            assert response.status_code == 200
            data = response.json()
            
            assert "timestamp" in data
            assert "total_metrics_tracked" in data
            assert "key_metrics" in data
            assert data["total_metrics_tracked"] == 2
    
    @pytest.mark.asyncio
    async def test_summary_includes_percentiles(self):
        """Test summary includes p95/p99"""
        metrics = PerformanceMetrics()
        
        # Record multiple values
        for i in range(100):
            await metrics.record("test", float(i))
        
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            response = client.get("/monitoring/performance/summary")
            data = response.json()
            
            key_metrics = data["key_metrics"]["test"]
            assert "p95_ms" in key_metrics
            assert "p99_ms" in key_metrics
            assert "mean_ms" in key_metrics


class TestConfigurationEndpoint:
    """Test configuration visibility endpoint"""
    
    def test_get_configuration(self):
        """Test GET /monitoring/config"""
        response = client.get("/monitoring/config")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "gitops" in data
        assert "version" in data
        assert data["version"] == "0.8.0"
    
    def test_config_includes_settings(self):
        """Test config includes GitOps settings"""
        response = client.get("/monitoring/config")
        data = response.json()
        
        gitops = data["gitops"]
        
        # Verify key settings are present
        assert "storage" in gitops
        assert "fuzzy_search_enabled" in gitops
        assert "commit_gen_enabled" in gitops
        assert "fuzzy_threshold" in gitops
    
    def test_config_no_secrets(self):
        """Test config doesn't expose secrets"""
        response = client.get("/monitoring/config")
        data = response.json()
        
        # Verify no sensitive data
        json_str = str(data)
        assert "token" not in json_str.lower()
        assert "password" not in json_str.lower()
        assert "secret" not in json_str.lower()


class TestMonitoringIntegration:
    """Integration tests for monitoring endpoints"""
    
    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow"""
        # 1. Check health
        health = client.get("/monitoring/health")
        assert health.status_code == 200
        
        # 2. Record some metrics
        metrics = PerformanceMetrics()
        await metrics.record("integration_test", 100.0)
        
        # 3. Get metrics
        with patch('src.api.monitoring.get_metrics', return_value=metrics):
            metrics_response = client.get("/monitoring/metrics")
            assert metrics_response.status_code == 200
            
            # 4. Get summary
            summary = client.get("/monitoring/performance/summary")
            assert summary.status_code == 200
            
            # 5. Get config
            config = client.get("/monitoring/config")
            assert config.status_code == 200
    
    def test_all_monitoring_endpoints_accessible(self):
        """Test all monitoring endpoints are accessible"""
        endpoints = [
            "/monitoring/health",
            "/monitoring/metrics",
            "/monitoring/cache/stats",
            "/monitoring/performance/summary",
            "/monitoring/config"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"{endpoint} failed"
