"""
Ray Cluster Manager for distributed computing.

Handles Ray cluster connection and resource management.

Usage:
    from orchestration.distributed.ray_cluster import RayCluster

    # Local execution (all cores on this machine)
    cluster = RayCluster()
    cluster.connect()

    # Connect to existing cluster
    cluster = RayCluster(address="ray://192.168.1.100:10001")
    cluster.connect()

    # Check resources
    print(cluster.resources)
    # {'CPU': 20.0, 'memory': 80GB, ...}

Author: de_Funk Team
Date: December 2025
"""
from __future__ import annotations

import os
from typing import Dict, Optional, Any
from dataclasses import dataclass

from config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ClusterResources:
    """Cluster resource summary."""
    total_cpus: float = 0.0
    total_memory_gb: float = 0.0
    num_nodes: int = 0
    node_details: Dict[str, Any] = None

    def __post_init__(self):
        if self.node_details is None:
            self.node_details = {}


class RayCluster:
    """
    Manager for Ray cluster connections.

    Supports both local execution and distributed cluster mode.

    Features:
    - Auto-detection of cluster vs local mode
    - Resource monitoring
    - Graceful shutdown handling
    """

    def __init__(
        self,
        address: Optional[str] = None,
        num_cpus: Optional[int] = None,
        runtime_env: Optional[Dict] = None
    ):
        """
        Initialize Ray cluster manager.

        Args:
            address: Ray cluster address (None for local, "auto" for existing cluster,
                    or "ray://host:port" for specific cluster)
            num_cpus: Limit CPUs for local mode
            runtime_env: Ray runtime environment config
        """
        self.address = address
        self.num_cpus = num_cpus
        self.runtime_env = runtime_env or {}
        self._connected = False
        self._ray = None

    def connect(self) -> 'RayCluster':
        """
        Connect to Ray cluster or start local Ray instance.

        Returns:
            self for method chaining
        """
        try:
            import ray
            self._ray = ray
        except ImportError:
            raise ImportError(
                "Ray is not installed. Install with: pip install 'ray[default]'"
            )

        if self._ray.is_initialized():
            logger.info("Ray already initialized, reusing existing connection")
            self._connected = True
            return self

        try:
            init_kwargs = {}

            if self.address:
                init_kwargs['address'] = self.address
                logger.info(f"Connecting to Ray cluster at {self.address}...")
            else:
                logger.info("Starting local Ray instance...")
                if self.num_cpus:
                    init_kwargs['num_cpus'] = self.num_cpus

            if self.runtime_env:
                init_kwargs['runtime_env'] = self.runtime_env

            self._ray.init(**init_kwargs)
            self._connected = True

            # Log resources
            resources = self.resources
            logger.info(
                f"Ray connected: {resources.total_cpus:.0f} CPUs, "
                f"{resources.total_memory_gb:.1f}GB memory, "
                f"{resources.num_nodes} nodes"
            )

            return self

        except Exception as e:
            logger.error(f"Failed to connect to Ray: {e}")
            raise

    def disconnect(self):
        """Disconnect from Ray cluster."""
        if self._ray and self._ray.is_initialized():
            self._ray.shutdown()
            self._connected = False
            logger.info("Ray disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Ray."""
        return self._connected and self._ray and self._ray.is_initialized()

    @property
    def resources(self) -> ClusterResources:
        """Get cluster resource summary."""
        if not self.is_connected:
            return ClusterResources()

        try:
            cluster_resources = self._ray.cluster_resources()

            # Count nodes
            node_keys = [k for k in cluster_resources if k.startswith('node:')]
            num_nodes = len(node_keys)

            # Sum resources
            total_cpus = cluster_resources.get('CPU', 0)
            total_memory = cluster_resources.get('memory', 0)
            memory_gb = total_memory / (1024 ** 3)

            return ClusterResources(
                total_cpus=total_cpus,
                total_memory_gb=memory_gb,
                num_nodes=max(num_nodes, 1),
                node_details=dict(cluster_resources)
            )
        except Exception as e:
            logger.warning(f"Failed to get cluster resources: {e}")
            return ClusterResources()

    @property
    def available_resources(self) -> Dict[str, float]:
        """Get currently available (unused) resources."""
        if not self.is_connected:
            return {}
        return dict(self._ray.available_resources())

    def submit(self, func, *args, **kwargs):
        """
        Submit a function for remote execution.

        Args:
            func: Remote function decorated with @ray.remote
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Ray ObjectRef (future)
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Ray cluster")
        return func.remote(*args, **kwargs)

    def get(self, refs, timeout: Optional[float] = None):
        """
        Get results from Ray ObjectRefs.

        Args:
            refs: Single ObjectRef or list of ObjectRefs
            timeout: Optional timeout in seconds

        Returns:
            Result(s) from remote execution
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Ray cluster")
        return self._ray.get(refs, timeout=timeout)

    def wait(self, refs, num_returns: int = 1, timeout: Optional[float] = None):
        """
        Wait for some refs to complete.

        Args:
            refs: List of ObjectRefs
            num_returns: Number of refs to wait for
            timeout: Optional timeout

        Returns:
            Tuple of (ready, not_ready) ObjectRefs
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to Ray cluster")
        return self._ray.wait(refs, num_returns=num_returns, timeout=timeout)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False


def get_ray():
    """Get the Ray module if available."""
    try:
        import ray
        return ray
    except ImportError:
        return None
