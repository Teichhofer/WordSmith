import tomllib
from pathlib import Path

def test_pyproject_metadata():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    project = data["project"]
    assert project["name"] == "wordsmith"
    assert project["dependencies"] == []
    dev_deps = project.get("optional-dependencies", {}).get("dev", [])
    assert any(dep.startswith("pytest") for dep in dev_deps)
