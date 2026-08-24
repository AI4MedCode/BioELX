import os

# Repository root: <BIOELX_HOME>/code/common/constants.py -> <BIOELX_HOME>
BIOELX_HOME = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

# Default to <BIOELX_HOME>/data and <BIOELX_HOME>/output. Point the environment
# variables somewhere else if your datasets and results live outside the repo.
DATA_DIR = os.environ.get("BIOELX_DATA_DIR", os.path.join(BIOELX_HOME, "data"))
OUTPUT_DIR = os.environ.get("BIOELX_OUTPUT_DIR", os.path.join(BIOELX_HOME, "output"))
