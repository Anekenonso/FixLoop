import os
import shutil
import subprocess
from pathlib import Path
import pytest

@pytest.fixture
def sandbox_repo(tmp_path):
    root = Path(__file__).resolve().parent.parent
    template = root / "sandbox_template"
    
    # Copy template into tmp_path
    for item in template.iterdir():
        if item.is_dir():
            shutil.copytree(item, tmp_path / item.name)
        else:
            shutil.copy2(item, tmp_path / item.name)
            
    # Initialize git repo and make first commit
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "fixloop-fixture"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "fixture@localhost"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fixloop initial fixture commit"], cwd=str(tmp_path), check=True, capture_output=True)
    
    return tmp_path
