"""
Performance logging utilities for Open Interpreter.
This module provides functions to track and log performance metrics.
"""

import time
import os
import json
import psutil
import threading
import traceback
from datetime import datetime
from collections import deque

# Enable/disable performance logging with different verbosity levels
# 0 = disabled, 1 = minimal (critical metrics only), 2 = standard, 3 = verbose
PERFORMANCE_LOGGING_LEVEL = int(os.environ.get("OI_PERFORMANCE_LOGGING_LEVEL", "2"))
PERFORMANCE_LOGGING_ENABLED = PERFORMANCE_LOGGING_LEVEL > 0

# Logging configuration
LOG_FILE_PATH = os.environ.get("OI_PERFORMANCE_LOG_PATH", "performance_logs.jsonl")
MAX_LOG_FILE_SIZE = int(os.environ.get("OI_MAX_LOG_FILE_SIZE_MB", "10")) * 1024 * 1024  # 10MB by default
LOG_ROTATION_COUNT = int(os.environ.get("OI_LOG_ROTATION_COUNT", "3"))  # Keep 3 log files by default

# Memory usage tracking with efficient data structure (limited circular buffer)
MAX_MEMORY_SAMPLES = int(os.environ.get("OI_MAX_MEMORY_SAMPLES", "100"))
memory_samples = deque(maxlen=MAX_MEMORY_SAMPLES)

# In-memory metrics storage for quick analysis
metrics_buffer = deque(maxlen=1000)  # Keep last 1000 metrics in memory for analysis

# Thread-local storage for nested timers
thread_local = threading.local()

# Write lock to prevent concurrent file writes
log_file_lock = threading.Lock()

def _should_log_level(level):
    """Check if the specified level should be logged based on current configuration"""
    return PERFORMANCE_LOGGING_ENABLED and PERFORMANCE_LOGGING_LEVEL >= level

def _rotate_log_file_if_needed():
    """Rotate log file if it exceeds maximum size"""
    if not os.path.exists(LOG_FILE_PATH):
        return
        
    if os.path.getsize(LOG_FILE_PATH) < MAX_LOG_FILE_SIZE:
        return
        
    # Rotate existing log files
    for i in range(LOG_ROTATION_COUNT - 1, 0, -1):
        src = f"{LOG_FILE_PATH}.{i}" if i > 0 else LOG_FILE_PATH
        dst = f"{LOG_FILE_PATH}.{i+1}"
        
        if os.path.exists(src):
            if os.path.exists(dst):
                try:
                    os.remove(dst)
                except:
                    pass
            try:
                os.rename(src, dst)
            except:
                pass
    
    # Create new empty log file
    try:
        open(LOG_FILE_PATH, 'w').close()
    except:
        pass

def get_system_info():
    """Get basic system information for performance context"""
    info = {}
    try:
        info["cpu_count"] = psutil.cpu_count(logical=True)
        info["physical_cpu_count"] = psutil.cpu_count(logical=False)
        mem = psutil.virtual_memory()
        info["total_memory_mb"] = mem.total / (1024 * 1024)
        info["available_memory_mb"] = mem.available / (1024 * 1024)
        info["memory_percent"] = mem.percent
        info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        info["swap_memory_mb"] = psutil.swap_memory().total / (1024 * 1024)
    except:
        info["error"] = "Failed to get system info"
    return info

def log_performance_metric(category, operation, duration, metadata=None, level=2):
    """
    Log a performance metric to the console and optionally to a file.
    
    Args:
        category (str): Category of the operation (e.g., 'llm', 'message_processing')
        operation (str): Name of the operation being measured
        duration (float): Duration of the operation in seconds
        metadata (dict, optional): Additional metadata about the operation
        level (int): Logging level (1=critical, 2=standard, 3=verbose)
    """
    if not _should_log_level(level):
        return
    
    try:
        timestamp = datetime.now().isoformat()
        
        # Get current memory usage (only for standard+ logging)
        memory_mb = 0
        if _should_log_level(2):
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # Store memory sample
                memory_samples.append((timestamp, memory_mb))
            except:
                pass
        
        # Create log entry
        log_entry = {
            "timestamp": timestamp,
            "category": category,
            "operation": operation,
            "duration_seconds": round(duration, 4),
            "memory_mb": round(memory_mb, 2),
            "metadata": metadata or {}
        }
        
        # Add to in-memory buffer
        metrics_buffer.append(log_entry)
        
        # Print to console based on verbosity
        if level == 1 or (level == 2 and duration > 0.5) or PERFORMANCE_LOGGING_LEVEL >= 3:
            print(f"[PERFORMANCE] {category}.{operation}: {duration:.4f}s" + 
                 (f", Memory: {memory_mb:.2f}MB" if _should_log_level(2) else ""))
        
        # Write to log file (thread-safe)
        if _should_log_level(2):
            with log_file_lock:
                try:
                    _rotate_log_file_if_needed()
                    with open(LOG_FILE_PATH, "a") as f:
                        f.write(json.dumps(log_entry) + "\n")
                except Exception as e:
                    if _should_log_level(3):
                        print(f"[PERFORMANCE] Failed to write to log file: {e}")
    except Exception as e:
        if _should_log_level(3):
            print(f"[PERFORMANCE] Error in logging: {str(e)}")

class PerformanceTimer:
    """
    Context manager for timing code blocks with support for nested timers
    and hierarchical performance tracking.
    """
    
    def __init__(self, category, operation, metadata=None, level=2):
        self.category = category
        self.operation = operation
        self.metadata = metadata or {}
        self.level = level
        self.start_time = None
        self.parent_timer = None
        self.depth = 0
    
    def __enter__(self):
        # Track timer start time
        self.start_time = time.time()
        
        # Handle nested timers
        if not hasattr(thread_local, "current_timer"):
            thread_local.current_timer = None
        
        self.parent_timer = thread_local.current_timer
        if self.parent_timer:
            self.depth = self.parent_timer.depth + 1
            # Add thread_id to metadata for debugging nested timers
            self.metadata["parent"] = f"{self.parent_timer.category}.{self.parent_timer.operation}"
            self.metadata["depth"] = self.depth
        
        # Set this as the current timer
        thread_local.current_timer = self
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            # Calculate duration
            duration = time.time() - self.start_time
            
            # Add exception info if applicable
            if exc_type:
                self.metadata["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_val),
                }
                # Higher logging level for errors
                log_level = 1
            else:
                log_level = self.level
            
            # Log the performance metric
            log_performance_metric(
                self.category, 
                self.operation, 
                duration, 
                self.metadata,
                level=log_level
            )
            
            # Restore parent timer
            thread_local.current_timer = self.parent_timer

def get_memory_trend():
    """
    Analyze memory usage trend and return a summary.
    
    Returns:
        dict: Memory trend summary
    """
    if not _should_log_level(2) or len(memory_samples) < 2:
        return {"trend": "insufficient_data"}
    
    first_sample = memory_samples[0][1]  # Memory value from first sample
    last_sample = memory_samples[-1][1]  # Memory value from last sample
    
    # Calculate memory growth
    memory_growth = last_sample - first_sample
    
    # Check if memory growth is significant (>1MB)
    significant = abs(memory_growth) > 1.0
    
    # Calculate rate of change (MB/minute)
    first_time = datetime.fromisoformat(memory_samples[0][0])
    last_time = datetime.fromisoformat(memory_samples[-1][0])
    time_diff_seconds = (last_time - first_time).total_seconds()
    
    if time_diff_seconds > 0:
        memory_growth_rate = (memory_growth / time_diff_seconds) * 60  # MB/minute
    else:
        memory_growth_rate = 0
    
    # Get min and max memory
    memory_values = [sample[1] for sample in memory_samples]
    min_memory = min(memory_values)
    max_memory = max(memory_values)
    
    return {
        "initial_memory_mb": round(first_sample, 2),
        "current_memory_mb": round(last_sample, 2),
        "min_memory_mb": round(min_memory, 2),
        "max_memory_mb": round(max_memory, 2),
        "total_growth_mb": round(memory_growth, 2),
        "growth_rate_mb_per_minute": round(memory_growth_rate, 2),
        "num_samples": len(memory_samples),
        "time_window_seconds": round(time_diff_seconds, 1),
        "trend": "stable" if not significant else "increasing" if memory_growth > 0 else "decreasing"
    }

def log_message_stats(messages):
    """
    Log statistics about the message history.
    
    Args:
        messages (list): List of message objects
    """
    if not _should_log_level(2) or not messages:
        return {}
    
    try:
        total_messages = len(messages)
        message_types = {}
        role_counts = {}
        total_content_length = 0
        max_message_size = 0
        code_blocks_count = 0
        console_output_count = 0
        image_count = 0
        
        # Loop through messages just once for efficiency
        for msg in messages:
            # Count by message type
            msg_type = msg.get("type", "unknown")
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
            
            # Count by role
            role = msg.get("role", "unknown")
            role_counts[role] = role_counts.get(role, 0) + 1
            
            # Track special message types
            if msg_type == "code":
                code_blocks_count += 1
            elif msg_type == "console" and msg.get("format") == "output":
                console_output_count += 1
            elif msg_type == "image":
                image_count += 1
            
            # Calculate content length
            content = msg.get("content", "")
            if isinstance(content, str):
                content_len = len(content)
                total_content_length += content_len
                max_message_size = max(max_message_size, content_len)
        
        stats = {
            "total_messages": total_messages,
            "message_types": message_types,
            "role_counts": role_counts,
            "total_content_length": total_content_length,
            "max_message_size": max_message_size,
            "avg_message_size": round(total_content_length / total_messages, 2),
            "code_blocks_count": code_blocks_count,
            "console_output_count": console_output_count,
            "image_count": image_count,
        }
        
        # Only log if we have enough context to be useful
        if total_messages > 1:
            log_performance_metric("messages", "stats", 0, stats, level=2)
        
        return stats
    except Exception as e:
        if _should_log_level(3):
            print(f"[PERFORMANCE] Error in message stats logging: {str(e)}")
        return {}

def get_hotspots(threshold_seconds=0.5, top_n=5):
    """
    Identify performance hotspots based on recent metrics.
    
    Args:
        threshold_seconds (float): Minimum duration to consider as a hotspot
        top_n (int): Number of top hotspots to return
    
    Returns:
        list: Top N performance hotspots
    """
    if not metrics_buffer:
        return []
    
    # Group by category and operation
    operation_stats = {}
    for metric in metrics_buffer:
        key = f"{metric['category']}.{metric['operation']}"
        if key not in operation_stats:
            operation_stats[key] = {
                "category": metric["category"],
                "operation": metric["operation"],
                "count": 0,
                "total_duration": 0,
                "max_duration": 0,
                "min_duration": float('inf'),
                "avg_duration": 0
            }
        
        stats = operation_stats[key]
        duration = metric["duration_seconds"]
        
        stats["count"] += 1
        stats["total_duration"] += duration
        stats["max_duration"] = max(stats["max_duration"], duration)
        stats["min_duration"] = min(stats["min_duration"], duration)
        stats["avg_duration"] = stats["total_duration"] / stats["count"]
    
    # Filter by threshold and sort by average duration
    hotspots = [
        stats for stats in operation_stats.values()
        if stats["avg_duration"] >= threshold_seconds
    ]
    
    hotspots.sort(key=lambda x: x["avg_duration"], reverse=True)
    
    # Return top N hotspots
    return hotspots[:top_n]

def report_performance_summary():
    """
    Generate a comprehensive performance report.
    
    Returns:
        dict: Performance summary
    """
    if not _should_log_level(1):
        return {"enabled": False}
    
    try:
        # Get memory trend
        mem_trend = get_memory_trend()
        
        # Get system info
        sys_info = get_system_info()
        
        # Get hotspots
        hotspots = get_hotspots()
        
        # Build summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "memory": mem_trend,
            "system": sys_info,
            "hotspots": hotspots,
            "metrics_count": len(metrics_buffer),
            "enabled": True,
            "level": PERFORMANCE_LOGGING_LEVEL
        }
        
        if _should_log_level(2):
            summary["log_file"] = {
                "path": os.path.abspath(LOG_FILE_PATH),
                "size_mb": round(os.path.getsize(LOG_FILE_PATH) / (1024 * 1024), 2) if os.path.exists(LOG_FILE_PATH) else 0,
                "max_size_mb": MAX_LOG_FILE_SIZE / (1024 * 1024),
                "rotation_count": LOG_ROTATION_COUNT
            }
        
        # Log summary
        if _should_log_level(3):
            print(f"[PERFORMANCE] Summary: {json.dumps(summary, indent=2)}")
            
        return summary
    except Exception as e:
        error_info = {
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        if _should_log_level(3):
            print(f"[PERFORMANCE] Error generating summary: {str(e)}")
        return {"error": error_info, "enabled": True}