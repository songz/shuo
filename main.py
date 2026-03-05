#!/usr/bin/env python3
"""
shuo - Voice Agent Framework

Usage:
    python main.py                  # local microphone/speaker mode

Runs the local conversation loop directly.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

from shuo.log import setup_logging, Logger, get_logger
from shuo.conversation import run_conversation_local

# Load environment variables
load_dotenv()

# Setup logging
setup_logging()
logger = get_logger("shuo")


def check_environment() -> bool:
    """Check that all required environment variables are set."""
    required_vars = [
        "DEEPGRAM_API_KEY",
        "ELEVENLABS_API_KEY",
    ]
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("ANTHROPIC_API_KEY")):
        logger.error("Missing environment variables: OPENAI_API_KEY or GROQ_API_KEY or ANTHROPIC_API_KEY")
        return False

    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        return False
    
    return True

def main():
    # Check environment
    if not check_environment():
        sys.exit(1)

    try:
        logger.info("Local mode — microphone/speaker (Ctrl+C to end)")
        asyncio.run(run_conversation_local())
    except KeyboardInterrupt:
        Logger.shutdown()
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
