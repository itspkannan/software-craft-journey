# Data structures & algorithms

Parallel Jupyter environments under this folder:

| Subfolder | Language | Lab URL (defaults) |
|-----------|----------|-------------------|
| **[PythonDSA](PythonDSA/)** | Python (SciPy stack) | http://localhost:8888/lab |
| **[JavaDSA](JavaDSA/)** | Java (IJava / JShell) | http://localhost:8889/lab |
| **[GoDSA](GoDSA/)** | Go (gophernotes) | http://localhost:8890/lab |

Each has its own `Dockerfile`, `docker-compose.yml`, `Makefile`, and `podman.md`. Topic layout (`linear/`, `nonlinear/`, `search/`, `notebooks/`) is shared so you can work the same subjects in whichever language you choose.

## Quick start

**Python**

```bash
cd DSA/PythonDSA
make vm-start && make start
```

**Java**

```bash
cd DSA/JavaDSA
make vm-start && make start
```

**Go**

```bash
cd DSA/GoDSA
make vm-start && make build && make start
```

You can run all three stacks at once (different host ports).

## Maintainer: refresh Java / Go topic notebooks

Optional scripts that overwrite generated topic notebooks in each track (they skip each track’s `notebooks/getting_started.ipynb`). From the repository root:

```bash
./DSA/scripts/refresh_java_notebooks.py
./DSA/scripts/refresh_go_notebooks.py
```

If `./…` fails with “permission denied”, mark the scripts executable once from the repo root: `chmod +x DSA/scripts/refresh_java_notebooks.py DSA/scripts/refresh_go_notebooks.py`.
