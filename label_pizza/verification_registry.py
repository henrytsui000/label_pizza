"""
Verification Function Registry
Automatically loads verification functions from multiple workspace folders
"""

import importlib.util
import sys
import json
import inspect
from typing import Dict, Callable, Optional, List, Set
from pathlib import Path
import os

def _same_source(fn_a: Callable, fn_b: Callable) -> bool:
    """True if two functions have identical source (best-effort).

    Used to treat duplicate verify.py definitions across workspaces as
    harmless when they are byte-for-byte the same. Falls back to comparing
    bytecode if source is unavailable.
    """
    try:
        return inspect.getsource(fn_a) == inspect.getsource(fn_b)
    except (OSError, TypeError):
        try:
            return fn_a.__code__.co_code == fn_b.__code__.co_code
        except AttributeError:
            return False


class VerificationRegistry:
    """Registry for verification functions from multiple workspaces"""
    
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        self._loaded_workspaces: Set[str] = set()
        self._function_sources: Dict[str, str] = {}  # Track which workspace each function came from
    
    def register_workspace(self, workspace_path: str) -> None:
        """Register verification functions from a workspace folder"""
        workspace_path = Path(workspace_path).resolve()
        verify_file = workspace_path / "verify.py"
        
        if not verify_file.exists():
            return  # No verification functions in this workspace
        
        workspace_str = str(workspace_path)
        if workspace_str in self._loaded_workspaces:
            return  # Already loaded
        
        try:
            # Load the verify module from workspace
            spec = importlib.util.spec_from_file_location(
                f"verify_{workspace_path.name}", 
                verify_file
            )
            verify_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verify_module)
            
            # Register all functions from this module
            for name, obj in inspect.getmembers(verify_module):
                if (inspect.isfunction(obj) and
                    not name.startswith('_')):
                    # Name collision across workspaces: keep the first-registered
                    # function instead of aborting this whole workspace. Aborting
                    # made function availability depend on workspace load order,
                    # which could leave a needed function (e.g. the one a shared
                    # question group references) unregistered. Only warn when the
                    # two definitions actually differ.
                    if name in self._functions:
                        existing_source = self._function_sources[name]
                        if _same_source(self._functions[name], obj):
                            continue  # identical duplicate — silently keep first
                        print(
                            f"Warning: Verification function '{name}' is defined "
                            f"differently in '{existing_source}' and '{workspace_str}'. "
                            f"Keeping the definition from '{existing_source}'."
                        )
                        continue
                    self._functions[name] = obj
                    self._function_sources[name] = workspace_str

            self._loaded_workspaces.add(workspace_str)
            
        except Exception as e:
            print(f"Warning: Could not load verification functions from {verify_file}: {e}")
    
    def get_function(self, function_name: str) -> Optional[Callable]:
        """Get a verification function by name"""
        return self._functions.get(function_name)
    
    def has_function(self, function_name: str) -> bool:
        """Check if a verification function exists"""
        return function_name in self._functions
    
    def list_functions(self) -> List[str]:
        """List all available verification functions"""
        return sorted(self._functions.keys())
    
    def get_function_source(self, function_name: str) -> Optional[str]:
        """Get the workspace path where function was loaded from"""
        return self._function_sources.get(function_name)
    
    def clear(self) -> None:
        """Clear all registered functions"""
        self._functions.clear()
        self._loaded_workspaces.clear()
        self._function_sources.clear()


# Global registry instance
_registry = VerificationRegistry()

def register_workspace(workspace_path: str) -> None:
    """Register verification functions from workspace"""
    _registry.register_workspace(workspace_path)

def get_verification_function(function_name: str) -> Optional[Callable]:
    """Get verification function by name"""
    return _registry.get_function(function_name)

def has_verification_function(function_name: str) -> bool:
    """Check if verification function exists"""
    return _registry.has_function(function_name)

def list_verification_functions() -> List[str]:
    """List all available verification functions"""
    return _registry.list_functions()

def get_verification_function_source(function_name: str) -> Optional[str]:
    """Get workspace path where function was loaded from"""
    return _registry.get_function_source(function_name)

def clear_registry() -> None:
    """Clear all registered functions (useful for testing)"""
    _registry.clear()


def load_verification_config() -> List[str]:
    """Load workspace paths from config file"""
    config_file = Path("verification_config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get("workspace_paths", [])
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not read verification_config.json: {e}")
    return []


def auto_load_workspaces() -> None:
    """Automatically load all workspaces from config"""
    workspace_paths = load_verification_config()
    for workspace_path in workspace_paths:
        if Path(workspace_path).exists():
            register_workspace(workspace_path)


class VerifyModule:
    """Backward-compatible wrapper that makes registry behave like old verify module"""
    
    def __getattr__(self, name: str):
        """Get verification function by name (supports getattr(verify, function_name))"""
        func = get_verification_function(name)
        if func is not None:
            return func
        raise AttributeError(f"module 'verify' has no attribute '{name}'")
    
    def __hasattr__(self, name: str) -> bool:
        """Check if verification function exists (supports hasattr(verify, function_name))"""
        return has_verification_function(name)
    
    def __dir__(self):
        """Support dir(verify) to list all functions"""
        return list_verification_functions()


# Create backward-compatible verify module instance
verify = VerifyModule()

# Auto-load workspaces when module is imported
auto_load_workspaces()