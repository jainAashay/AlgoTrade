"""
Configuration loader module.

Provides a singleton Config class for loading and accessing YAML configuration files.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Optional
import logging
import re

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class Config:
    """
    Singleton configuration manager.
    
    Loads configuration from a YAML file and provides access to nested configuration
    values using dot-notation style keys.
    """
    _cfg: Optional[dict] = None
    _config_path: Optional[Path] = None

    @classmethod
    def load(cls, path: Optional[str] = None) -> None:
        """
        Load configuration from a YAML file.
        
        Args:
            path: Path to the configuration file. If None, uses default location
                  (configs/config.yml relative to project root).
                  
        Raises:
            ConfigurationError: If the config file cannot be loaded.
        """
        if path is None:
            # Default to configs/config.yml relative to project root
            project_root = Path(__file__).parent.parent
            path = str(project_root / "configs" / "config.yml")
        
        config_path = Path(path)
        
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Substitute environment variables (works for both local and production)
                content = cls._substitute_env_vars(content)
                cls._cfg = yaml.safe_load(content)
            cls._config_path = config_path
            logger.info(f"Configuration loaded from {config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Error parsing YAML configuration: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")

    @classmethod
    def get(cls, *keys: str, default: Any = None) -> Any:
        """
        Get a configuration value using nested keys.
        
        Args:
            *keys: One or more keys to navigate the configuration tree.
            default: Default value to return if key is not found.
            
        Returns:
            The configuration value at the specified path.
            
        Raises:
            ConfigurationError: If configuration is not loaded or key is missing.
        """
        if cls._cfg is None:
            raise ConfigurationError("Configuration not loaded. Call Config.load() first.")
        
        data = cls._cfg
        try:
            for k in keys:
                data = data[k]
            return data
        except (KeyError, TypeError) as e:
            if default is not None:
                return default
            raise ConfigurationError(f"Configuration key not found: {' -> '.join(keys)}") from e

    @classmethod
    def is_loaded(cls) -> bool:
        """Check if configuration has been loaded."""
        return cls._cfg is not None

    @classmethod
    def get_path(cls) -> Optional[Path]:
        """Get the path of the loaded configuration file."""
        return cls._config_path

    @classmethod
    def _substitute_env_vars(cls, content: str) -> str:
        """
        Substitute environment variables in the configuration content.
        
        Supports ${VAR_NAME} and $VAR_NAME syntax.
        If environment variable is not found, leaves the placeholder unchanged.
        This allows the same config to work locally (with .env file) and in production.
        """
        # Pattern to match ${VAR_NAME} or $VAR_NAME
        pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
        
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            env_value = os.getenv(var_name)
            if env_value is None:
                # For local development, try to load from .env file
                cls._load_env_file()
                env_value = os.getenv(var_name)
                if env_value is None:
                    logger.warning(f"Environment variable '{var_name}' not found, keeping placeholder")
                    return match.group(0)  # Return original placeholder
            return env_value
        
        return re.sub(pattern, replace_var, content)

    @classmethod
    def _load_env_file(cls) -> None:
        """Load environment variables from .env file if it exists."""
        env_file = Path(__file__).parent.parent / ".env"
        if env_file.exists() and not hasattr(cls, '_env_loaded'):
            try:
                with open(env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            # Remove quotes if present
                            value = value.strip('"\'')
                            os.environ[key] = value
                cls._env_loaded = True
                logger.info(f"Loaded environment variables from {env_file}")
            except Exception as e:
                logger.warning(f"Could not load .env file: {e}")
