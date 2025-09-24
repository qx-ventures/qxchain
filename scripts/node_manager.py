#!/usr/bin/env python3
"""
QX Chain Node Manager

This module provides functionality to start, stop, and manage blockchain nodes
alongside worker and validator processes.
"""

import os
import sys
import subprocess
import asyncio
import time
import signal
import socket
import requests
from pathlib import Path
from typing import Optional, Dict, Any

class NodeManager:
    def __init__(self, 
                 node_name: str,
                 ws_port: int = 9933,
                 http_port: int = 9933,
                 p2p_port: int = 30333,
                 consensus: str = "instant-seal",
                 chain_spec: str = "dev"):
        
        self.node_name = node_name
        self.ws_port = ws_port
        self.http_port = http_port  
        self.p2p_port = p2p_port
        self.consensus = consensus
        self.chain_spec = chain_spec
        
        # Process management
        self.node_process: Optional[subprocess.Popen] = None
        self.is_running = False
        
        # Paths
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        self.binary_path = self.project_root / "target" / "release" / "qxchain"
        self.logs_dir = self.project_root / "logs"
        self.data_dir = self.project_root / "data" / self.node_name
        
        # Create directories
        self.logs_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Log files
        self.log_file = self.logs_dir / f"{self.node_name}_node.log"
        self.startup_log = self.logs_dir / f"{self.node_name}_startup.log"
        
        print(f"🔧 Node Manager initialized for: {self.node_name}")
        print(f"   WS Port: {self.ws_port}")
        print(f"   HTTP Port: {self.http_port}")
        print(f"   P2P Port: {self.p2p_port}")
        print(f"   Data Dir: {self.data_dir}")
    
    def is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def kill_port(self, port: int):
        """Kill any process using the given port"""
        try:
            # Find process using port
            result = subprocess.run(['lsof', '-ti', f':{port}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"🔄 Killed process {pid} on port {port}")
                        time.sleep(1)
                        # Force kill if still running
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    except (ValueError, ProcessLookupError):
                        pass
        except Exception as e:
            print(f"⚠️ Error killing port {port}: {e}")
    
    def check_binary(self) -> bool:
        """Check if the qxchain binary exists"""
        if not self.binary_path.exists():
            print(f"❌ Binary not found: {self.binary_path}")
            print("💡 Run './scripts/build_chain.sh' first")
            return False
        return True
    
    def generate_node_key(self) -> str:
        """Generate a unique node key for this node"""
        import hashlib
        # Create a deterministic node key based on node name
        key_material = f"{self.node_name}-{self.ws_port}".encode()
        return hashlib.sha256(key_material).hexdigest()[:64]
    
    async def start_node(self, 
                        bootnode: Optional[str] = None,
                        validator: bool = False,
                        alice: bool = False) -> bool:
        """Start the blockchain node"""
        
        if not self.check_binary():
            return False
        
        # Kill any existing processes on our ports
        for port in [self.ws_port, self.p2p_port]:  # qxchain only uses ws_port for RPC/WS
            if self.is_port_in_use(port):
                print(f"🔄 Port {port} in use, killing existing process...")
                self.kill_port(port)
                await asyncio.sleep(2)
        
        # Build command (note: qxchain uses --rpc-port for WebSocket, not --ws-port)
        cmd = [
            str(self.binary_path),
            f"--name={self.node_name}",
            f"--base-path={self.data_dir}",
            f"--chain={self.chain_spec}",
            f"--rpc-port={self.ws_port}",  # qxchain uses rpc-port for WebSocket
            f"--port={self.p2p_port}",
            "--rpc-cors=all",
            "--rpc-methods=unsafe",
            f"--consensus={self.consensus}",
            "--detailed-log-output",
            "--log=info"
        ]
        
        # Add validator flag if needed
        if validator:
            cmd.append("--validator")
        
        # Add alice flag for testing
        if alice:
            cmd.append("--alice")
        else:
            # Use unique node key
            node_key = self.generate_node_key()
            cmd.extend(["--node-key", node_key])
        
        # Add bootnode if provided
        if bootnode:
            cmd.extend(["--bootnodes", bootnode])
        
        # For non-alice nodes, don't use --tmp to maintain state
        if not alice:
            pass  # Don't add --tmp, let node maintain its data
        else:
            cmd.append("--tmp")  # Alice uses temporary storage
        
        print(f"🚀 Starting blockchain node: {self.node_name}")
        print(f"📋 Command: {' '.join(cmd)}")
        
        try:
            # Start node process
            with open(self.log_file, 'w') as log_f, open(self.startup_log, 'w') as startup_f:
                self.node_process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    cwd=self.project_root,
                    preexec_fn=os.setsid  # Create new process group
                )
            
            # Wait a bit for startup
            await asyncio.sleep(3)
            
            # Check if process is still running
            if self.node_process.poll() is not None:
                print(f"❌ Node process exited immediately")
                return False
            
            # Wait for RPC to be ready
            if await self.wait_for_rpc():
                self.is_running = True
                print(f"✅ Node {self.node_name} started successfully")
                print(f"🌐 WebSocket: ws://localhost:{self.ws_port}")
                print(f"🌐 HTTP RPC: http://localhost:{self.http_port}")
                return True
            else:
                print(f"❌ Node {self.node_name} failed to start properly")
                await self.stop_node()
                return False
                
        except Exception as e:
            print(f"❌ Error starting node: {e}")
            return False
    
    async def wait_for_rpc(self, timeout: int = 60) -> bool:
        """Wait for node RPC to be ready"""
        print(f"⏳ Waiting for {self.node_name} RPC to be ready...")
        
        url = f"http://localhost:{self.ws_port}"  # qxchain serves RPC on the same port as WebSocket
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.post(
                    url,
                    json={
                        "id": 1,
                        "jsonrpc": "2.0",
                        "method": "system_health",
                        "params": []
                    },
                    timeout=5
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if "result" in data:
                        print(f"✅ {self.node_name} RPC is ready!")
                        return True
                        
            except (requests.exceptions.RequestException, ValueError):
                pass
            
            print(f"⏳ Waiting for {self.node_name} RPC... ({int(time.time() - start_time)}s)")
            await asyncio.sleep(3)
        
        print(f"❌ {self.node_name} RPC failed to become ready within {timeout}s")
        return False
    
    async def stop_node(self):
        """Stop the blockchain node"""
        if self.node_process:
            print(f"🛑 Stopping node: {self.node_name}")
            
            try:
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(self.node_process.pid), signal.SIGTERM)
                
                # Wait for graceful shutdown
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(self.node_process.wait), 
                        timeout=10
                    )
                except asyncio.TimeoutError:
                    # Force kill if not stopped gracefully
                    print(f"⚠️ Force killing node: {self.node_name}")
                    os.killpg(os.getpgid(self.node_process.pid), signal.SIGKILL)
                    
            except (ProcessLookupError, OSError):
                pass  # Process already dead
            
            self.node_process = None
            self.is_running = False
            print(f"✅ Node {self.node_name} stopped")
    
    def get_node_info(self) -> Dict[str, Any]:
        """Get node information"""
        return {
            "name": self.node_name,
            "running": self.is_running,
            "ws_port": self.ws_port,
            "http_port": self.http_port,
            "p2p_port": self.p2p_port,
            "ws_endpoint": f"ws://localhost:{self.ws_port}",
            "http_endpoint": f"http://localhost:{self.ws_port}",  # Same port for qxchain
            "data_dir": str(self.data_dir),
            "log_file": str(self.log_file),
            "pid": self.node_process.pid if self.node_process else None
        }
    
    async def get_node_status(self) -> Dict[str, Any]:
        """Get detailed node status from RPC"""
        if not self.is_running:
            return {"status": "stopped"}
        
        try:
            url = f"http://localhost:{self.ws_port}"  # qxchain serves RPC on same port
            
            # Get system health
            health_response = requests.post(
                url,
                json={
                    "id": 1,
                    "jsonrpc": "2.0", 
                    "method": "system_health",
                    "params": []
                },
                timeout=5
            )
            
            # Get system info
            info_response = requests.post(
                url,
                json={
                    "id": 2,
                    "jsonrpc": "2.0",
                    "method": "system_properties", 
                    "params": []
                },
                timeout=5
            )
            
            status = {"status": "running"}
            
            if health_response.status_code == 200:
                health_data = health_response.json()
                if "result" in health_data:
                    status["health"] = health_data["result"]
            
            if info_response.status_code == 200:
                info_data = info_response.json()
                if "result" in info_data:
                    status["properties"] = info_data["result"]
            
            return status
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_peer_id(self) -> Optional[str]:
        """Get the node's peer ID"""
        try:
            url = f"http://localhost:{self.ws_port}"  # qxchain serves RPC on same port
            response = requests.post(
                url,
                json={
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "system_localPeerId",
                    "params": []
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    return data["result"]
                    
        except Exception as e:
            print(f"❌ Error getting peer ID: {e}")
        
        return None

# Utility functions for common node setups
def create_worker_node_manager(worker_name: str, base_port: int = 9933) -> NodeManager:
    """Create a node manager for a worker"""
    return NodeManager(
        node_name=f"worker_{worker_name}",
        ws_port=base_port,
        http_port=base_port + 100,  # HTTP port = WS port + 100
        p2p_port=base_port + 200,   # P2P port = WS port + 200
        consensus="instant-seal"
    )

def create_validator_node_manager(validator_name: str, base_port: int = 9955) -> NodeManager:
    """Create a node manager for a validator"""
    return NodeManager(
        node_name=f"validator_{validator_name}",
        ws_port=base_port,
        http_port=base_port + 100,
        p2p_port=base_port + 200,
        consensus="instant-seal"
    )

# Auto-assign ports based on process ID to avoid conflicts
def get_auto_ports(base_port: int = 9933) -> tuple[int, int, int]:
    """Get automatically assigned ports to avoid conflicts"""
    import hashlib
    import os
    
    # Use process ID and timestamp to generate unique port offset
    pid = os.getpid()
    offset = (pid % 100) * 10  # Max 100 processes, 10 ports apart
    
    ws_port = base_port + offset
    http_port = ws_port  # qxchain uses same port for RPC and WebSocket
    p2p_port = ws_port + 2000
    
    return ws_port, http_port, p2p_port
