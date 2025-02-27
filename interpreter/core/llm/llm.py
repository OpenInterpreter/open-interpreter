import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import sys
import logging
import time
import uuid
import json
import threading
from functools import lru_cache

import litellm
import requests
import tokentrim as tt

litellm.suppress_debug_info = True
litellm.REPEATED_STREAMING_CHUNK_LIMIT = 99999999

from ..utils.performance_logger import PerformanceTimer, log_performance_metric

from .run_text_llm import run_text_llm
from .run_tool_calling_llm import run_tool_calling_llm
from .utils.convert_to_openai_messages import convert_to_openai_messages

# Create or get the logger
logger = logging.getLogger("LiteLLM")


class SuppressDebugFilter(logging.Filter):
    def filter(self, record):
        return record.levelno >= logging.INFO


# Apply the filter
logger.addFilter(SuppressDebugFilter())


# Thread-local storage for LLM-related data
thread_local = threading.local()


class Llm:
    """
    A stateless LMC-style LLM with some helpful properties.
    """

    def __init__(self, interpreter):
        # Default properties
        self.interpreter = interpreter
        self.model = "gpt-4o"
        self.temperature = 0.0
        self.max_tokens = None
        self.context_window = None
        self.api_key = None
        self.api_base = None
        self.api_version = None
        self.max_budget = None
        self.supports_functions = True
        self.supports_vision = True
        self.supports_stream = True
        self.tokenizer = None
        self.timeout = 60  # Default timeout in seconds
        self.execution_instructions = True
        self.retry_attempts = 3
        self._request_timeout = 30  # HTTP request timeout
        self._model_cache = {}  # Cache for model-specific configurations
        
        # Performance monitoring
        self.track_performance = os.environ.get("OI_TRACK_LLM_PERFORMANCE", "True").lower() == "true"
        self._last_request_time = 0
        self._token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    def load(self):
        if "ollama" in self.model:
            try:
                # Check if Ollama is running
                requests.get("http://localhost:11434/api/version", timeout=1)
            except:
                # Start Ollama in the background if it's not running
                if os.name == "nt":  # Windows
                    os.system("start ollama serve")
                else:  # macOS/Linux
                    os.system("ollama serve &")
                # Wait for Ollama to start
                for _ in range(5):
                    time.sleep(1)
                    try:
                        requests.get("http://localhost:11434/api/version", timeout=1)
                        break
                    except:
                        continue
            
            # Pull the model if not already pulled
            model_name = self.model.replace("ollama/", "")
            try:
                models_response = requests.get("http://localhost:11434/api/tags", timeout=5).json()
                models = [m["name"] for m in models_response.get("models", [])]
                if model_name not in models:
                    print(f"Pulling model {model_name}...")
                    os.system(f"ollama pull {model_name}")
            except Exception as e:
                print(f"Error checking Ollama models: {str(e)}")

    @property
    def request_timeout(self):
        # Use a property to ensure we can't set it to None
        return self._request_timeout
    
    @request_timeout.setter
    def request_timeout(self, value):
        if value is not None:
            self._request_timeout = value
        
    @lru_cache(maxsize=32)
    def _get_model_config(self, model_name):
        """Cache and return model-specific configurations"""
        # This allows us to avoid redundant model config lookups
        if model_name in self._model_cache:
            return self._model_cache[model_name]
        
        # Determine model capabilities and configurations
        config = {
            "supports_functions": self.supports_functions,
            "supports_vision": self.supports_vision,
            "context_window": self.context_window,
            "max_tokens": self.max_tokens
        }
        
        # Model-specific overrides
        if "gpt-3.5" in model_name:
            config["context_window"] = config["context_window"] or 16385
        elif "gpt-4" in model_name and "o" in model_name:
            config["context_window"] = config["context_window"] or 128000
        elif "gpt-4" in model_name:
            config["context_window"] = config["context_window"] or 8192
        elif "claude" in model_name:
            config["context_window"] = config["context_window"] or 100000
        
        # Cache the config
        self._model_cache[model_name] = config
        return config

    def run(self, messages):
        """
        Process and run the LLM with the provided messages.
        Returns a generator that yields message chunks.
        """
        # Track request start time for performance monitoring
        request_start_time = time.time()
        
        # Process messages with performance tracking
        with PerformanceTimer("message_processing", "convert_to_openai_format"):
            # Fix messages format if needed
            if len(messages) > 0 and isinstance(messages[0], dict) and messages[0].get("role") == "system":
                system_message = messages[0]["content"]
                messages = messages[1:]
            else:
                system_message = ""

        # Trim messages to fit the context window
        with PerformanceTimer("message_processing", "token_trimming"):
            try:
                if self.context_window and self.max_tokens:
                    # Leave room for the completion
                    messages = tt.trim(
                        messages,
                        max_tokens=self.context_window - self.max_tokens,
                        system_message=system_message,
                    )
                elif self.context_window and not self.max_tokens:
                    # Use a default max_tokens if not specified
                    default_max_tokens = min(4096, int(self.context_window * 0.25))
                    messages = tt.trim(
                        messages,
                        max_tokens=self.context_window - default_max_tokens,
                        system_message=system_message,
                    )
                else:
                    # No trimming needed
                    pass
            except Exception as e:
                # If trimming fails, continue with the original messages
                print(f"Warning: Token trimming failed: {e}")
        
        # Setup parameters for LLM call
        params = {
            "model": self.model,
            "messages": convert_to_openai_messages(
                [{"role": "system", "content": system_message}] + messages,
                function_calling=self.supports_functions,
            ),
            "temperature": self.temperature,
            "stream": self.supports_stream,
            "timeout": self.timeout,
        }

        # Add API-specific parameters
        if self.api_key:
            params["api_key"] = self.api_key
        if self.api_base:
            params["api_base"] = self.api_base
        if self.api_version:
            params["api_version"] = self.api_version
        if self.max_tokens:
            params["max_tokens"] = self.max_tokens

        # Optimize parameters for specific models
        self._optimize_params_for_model(params)
        
        # Run the LLM with retry logic
        for response_chunk in self._run_with_retries(params):
            yield response_chunk
            
        # Log performance data after completion
        if self.track_performance:
            elapsed_time = time.time() - request_start_time
            log_performance_metric("llm", "api_call", elapsed_time, {
                "model": self.model,
                "token_count": self._token_usage.get("total_tokens", 0)
            })

    def _optimize_params_for_model(self, params):
        """Apply model-specific optimizations to parameters"""
        model = params.get("model", "")
        
        # For local models, add helpful stop sequences
        if "local" in model:
            params["stop"] = ["<|assistant|>", "<|end|>", "<|eot_id|>"]
        
        # Handle special model cases
        if model == "i" and "conversation_id" in params:
            litellm.drop_params = False  # Don't drop this parameter for 'i' model
        else:
            litellm.drop_params = True
            
        # Remove ':latest' suffix which some providers don't handle well
        params["model"] = model.replace(":latest", "")
        
        # Set custom timeouts for different model types
        if "gpt-4" in model and "o" not in model:
            # GPT-4 non-o models can be slower
            self._request_timeout = max(60, self._request_timeout)
        elif "local" in model or "ollama" in model:
            # Local models may need more time for first run
            self._request_timeout = max(120, self._request_timeout)

    def _run_with_retries(self, params):
        """Run the LLM call with smart retry logic"""
        attempts = 0
        max_attempts = self.retry_attempts
        last_error = None
        backoff_factor = 1.5
        wait_time = 1  # Initial wait time in seconds
        
        # Create a unique request ID for tracking
        request_id = str(uuid.uuid4())
        
        while attempts < max_attempts:
            try:
                # Add a delay if this isn't the first attempt
                if attempts > 0:
                    time.sleep(wait_time)
                    wait_time *= backoff_factor  # Exponential backoff
                    
                # Log the attempt if in debug mode
                if self.interpreter.debug:
                    print(f"LLM request attempt {attempts+1}/{max_attempts} (ID: {request_id})")
                
                # Make the LLM call
                yield from self._execute_llm_call(params)
                
                # If we get here, the call succeeded
                return
                
            except KeyboardInterrupt:
                # Always allow user to cancel operations
                print("Exiting...")
                sys.exit(0)
                
            except litellm.exceptions.AuthenticationError as e:
                # If authentication fails and we're missing an API key, try with a dummy key
                if attempts == 0 and "api_key" not in params:
                    print("LiteLLM requires an API key. Trying again with a dummy API key.")
                    params["api_key"] = "x"
                else:
                    # Authentication errors don't benefit from retries
                    raise
            
            except Exception as e:
                # Store the error for potential re-raising
                last_error = e
                
                # For network-related errors, we should retry
                if "network" in str(e).lower() or "timeout" in str(e).lower():
                    attempts += 1
                    continue
                    
                # For rate limits, we should retry with backoff
                if isinstance(e, litellm.exceptions.RateLimitError):
                    attempts += 1
                    # Use a longer delay for rate limits
                    wait_time = max(wait_time, 5 * backoff_factor ** attempts)
                    continue
                    
                # For other errors, try one more attempt with slightly adjusted parameters
                if attempts == 0:
                    # Slightly adjust the temperature to potentially avoid deterministic errors
                    params["temperature"] = params.get("temperature", 0.0) + 0.1
                    attempts += 1
                    continue
                    
                # If we've exhausted attempts or can't handle this error type, re-raise
                raise
                
            finally:
                attempts += 1
        
        # If we've exhausted all retry attempts, raise the last error
        if last_error:
            raise last_error
        else:
            raise Exception(f"LLM request failed after {max_attempts} attempts for unknown reasons")

    def _execute_llm_call(self, params):
        """Execute the actual LLM call and track performance"""
        # Track token usage for this call
        local_token_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        
        # Execute the LLM call with performance tracking
        with PerformanceTimer("llm", "api_call", {"model": params.get("model", "unknown")}):
            try:
                # Configure request timeout
                if "timeout" not in params and self._request_timeout:
                    params["timeout"] = self._request_timeout
                    
                # Track time between requests to avoid overloading API
                time_since_last = time.time() - getattr(self, "_last_request_time", 0)
                if time_since_last < 0.1:
                    # Add a small delay to prevent rate limiting
                    time.sleep(0.1 - time_since_last)
                
                # Make the actual API call
                for chunk in litellm.completion(**params):
                    # Update token usage if available in the response
                    if hasattr(chunk, "usage") and chunk.usage:
                        local_token_usage["prompt_tokens"] = chunk.usage.get("prompt_tokens", 0)
                        local_token_usage["completion_tokens"] += chunk.usage.get("completion_tokens", 0)
                    
                    # Track the last request time
                    self._last_request_time = time.time()
                    
                    # Yield the chunk to the caller
                    yield chunk
                    
            finally:
                # Update the global token usage
                self._token_usage["prompt_tokens"] += local_token_usage["prompt_tokens"]
                self._token_usage["completion_tokens"] += local_token_usage["completion_tokens"]
                self._token_usage["total_tokens"] = self._token_usage["prompt_tokens"] + self._token_usage["completion_tokens"]
