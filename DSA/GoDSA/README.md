# Go coding practice (Jupyter)

Practice data structures and algorithms in **Go** with **Jupyter Lab** and the [**gophernotes**](https://github.com/gopherdata/gophernotes) kernel. Same Podman + `Makefile` + compose layout as the sibling DSA tracks.

## Quick start

```bash
cd DSA/GoDSA
make vm-start && make build && make start
```

Open **http://localhost:8890/lab** (no token). Choose the **Go** kernel for topic notebooks.

| Stack | Port |
|-------|------|
| Primary notebooks | 8888 |
| Java | 8889 |
| Go (this repo) | 8890 |

## Layout

Same tree as the other tracks (`linear/`, `nonlinear/`, `search/`, `notebooks/`, `data/`). Topic workbooks live under each topic folder.

`*_solutions.ipynb` files keep the same **markdown** as the course tree (problem framing, **Approach**, **Complexity**, and walkthroughs). Code cells add a **reference block comment** plus **Go** where the refresh tool can emit it; otherwise the full solution appears as **`//` lines** (course notation) with a compiling default return so you still have the logic and tests in one place.

## Refreshing topic notebooks

Maintainers can rebuild all topic `*.ipynb` files in this tree (except `notebooks/getting_started.ipynb`) from the repository root:

```bash
./DSA/scripts/refresh_go_notebooks.py
```

If `./…` fails with “permission denied”, run once from the repo root: `chmod +x DSA/scripts/refresh_go_notebooks.py`.

Re-run after you change the inputs the refresh script uses or adjust how notebooks are emitted (see the script docstring).

## Requirements

- Podman + `podman-compose` ([podman.md](podman.md))
- Same Podman machine as other stacks (`course-vm` in the Makefile by default)

## Go version

The image installs **Go 1.23.4** and **gophernotes v0.7.5** (pinned release tag from the upstream repo).

Hub overview: [../README.md](../README.md).
