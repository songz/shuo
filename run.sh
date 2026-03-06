#!/bin/bash
# Launcher script for the Tammy Face Display App

# Change to the script directory
cd "$(dirname "$0")"

# Activate virtual environment
source .venv/bin/activate

# Run the application
python3 main.py
# python3 list_input_devices.py
