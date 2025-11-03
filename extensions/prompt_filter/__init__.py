"""
Content Filter Extension for Fooocus
Validates prompts before image generation
"""

from .filter import ContentFilter

__version__ = "1.0.0"
__all__ = ['check_inappropriate_text']