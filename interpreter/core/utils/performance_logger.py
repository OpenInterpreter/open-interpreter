"""
Performance logging utilities for Open Interpreter.
This module provides functions to track and log performance metrics.
"""

import time
import os
import json
import psutil
from datetime import datetime

# Enable/disable performance logging
PERFORMANCE_LOGGING_ENABLED = os.environ.get("OI_PERFORMANCE_LOGGING", "True").lower() == "true"
LOG_FILE_PATH = os.environ.get("OI_PERFORMANCE_LOG_PATH", "performance_logs.jsonl")

# Track memory usage over time
memory_samples = []

def log_performance_metric(category, operation, duration, metadata=None):
    """
    Log a performance metric to the console and optionally to a file.
    
    Args:
        category (str): Category of the operation (e.g., 'llm', 'message_processing')
        operation (str): Name of the operation being measured
        duration (float): Duration of the operation in seconds
        metadata (dict, optional): Additional metadata about the operation
    """
    if not PERFORMANCE_LOGGING_ENABLED:
        return
    
    timestamp = datetime.now().isoformat()
    
    # Get current memory usage
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024
    
    # Store memory sample
    memory_samples.append((timestamp, memory_mb))
    
    # Keep only the last 100 samples to avoid memory bloat
    if len(memory_samples) > 100:
        memory_samples.pop(0)
    
    # Create log entry
    log_entry = {
        "timestamp": timestamp,
        "category": category,
        "operation": operation,
        "duration_seconds": round(duration, 4),
        "memory_mb": round(memory_mb, 2),
        "metadata": metadata or {}
    }
    
    # Print to console
    print(f"[PERFORMANCE] {category}.{operation}: {duration:.4f}s, Memory: {memory_mb:.2f}MB")
    
    # Write to log file
    try:
        with open(LOG_FILE_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        print(f"[PERFORMANCE] Failed to write to log file: {e}")

class PerformanceTimer:
    """Context manager for timing code blocks"""
    
    def __init__(self, category, operation, metadata=None):
        self.category = category
        self.operation = operation
        self.metadata = metadata
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            log_performance_metric(self.category, self.operation, duration, self.metadata)

def get_memory_trend():
    """
    Analyze memory usage trend and return a summary.
    
    Returns:
        dict: Memory trend summary
    """
    if len(memory_samples) < 2:
        return {"trend": "insufficient_data"}
    
    first_sample = memory_samples[0][1]  # Memory value from first sample
    last_sample = memory_samples[-1][1]  # Memory value from last sample
    
    # Calculate memory growth
    memory_growth = last_sample - first_sample
    
    # Calculate average growth per sample
    avg_growth_per_sample = memory_growth / (len(memory_samples) - 1)
    
    return {
        "initial_memory_mb": round(first_sample, 2),
        "current_memory_mb": round(last_sample, 2),
        "total_growth_mb": round(memory_growth, 2),
        "avg_growth_per_operation_mb": round(avg_growth_per_sample, 4),
        "num_samples": len(memory_samples),
        "trend": "increasing" if memory_growth > 0 else "stable_or_decreasing"
    }

def log_message_stats(messages):
    """
    Log statistics about the message history.
    
    Args:
        messages (list): List of message objects
    """
    if not PERFORMANCE_LOGGING_ENABLED:
        return
    
    total_messages = len(messages)
    message_types = {}
    total_content_length = 0
    
    for msg in messages:
        msg_type = msg.get("type", "unknown")
        message_types[msg_type] = message_types.get(msg_type, 0) + 1
        
        content = msg.get("content", "")
        if isinstance(content, str):
            total_content_length += len(content)
    
    metadata = {
        "total_messages": total_messages,
        "message_types": message_types,
        "total_content_length": total_content_length,
        "avg_message_size": round(total_content_length / max(total_messages, 1), 2)
    }
    
    log_performance_metric("messages", "stats", 0, metadata)
    return metadata