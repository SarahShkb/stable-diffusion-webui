import launch
import os

# Get the directory where this script is located
extension_dir = os.path.dirname(os.path.realpath(__file__))
requirements_file = os.path.join(extension_dir, "requirements.txt")

# Install from requirements.txt
if os.path.exists(requirements_file):
    launch.run_pip(f"install -r {requirements_file}", "prompt_filter extension requirements")