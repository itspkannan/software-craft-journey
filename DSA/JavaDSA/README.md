# Java coding practice (Jupyter)

Practice data structures and algorithms in **Java** inside **Jupyter Lab**, using the [IJava](https://github.com/SpencerPark/IJava) kernel (JShell-backed cells, `%classpath`, etc.). Uses the same Podman + `Makefile` + compose workflow as the other DSA tracks.

## Quick start

```bash
cd DSA/JavaDSA
make vm-start && make build && make start
```

Open **http://localhost:8889/lab** (no token). Choose the **Java** kernel for topic notebooks.

Sibling stacks use **8888** and **8890**; this service uses **8889** so they can run together.

## Layout

Same directory tree as the other tracks (`linear/`, `nonlinear/`, `search/`, `notebooks/`, `data/`). Topic workbooks live under each topic folder.

```text
JavaDSA/
├── data/
├── docker-compose.yml
├── Dockerfile
├── linear/
├── Makefile
├── nonlinear/
├── notebooks/
│   └── getting_started.ipynb
├── podman.md
├── README.md
└── search/
```

## Requirements

- Podman + `podman-compose` (see [podman.md](podman.md))
- Same Podman machine as other stacks (`course-vm` in the Makefile by default)

## Java version

The image ships **OpenJDK 21** (LTS) and **IJava 1.3.0**.

## Refreshing topic notebooks

Maintainers can rebuild all topic `*.ipynb` files in this tree (except `notebooks/getting_started.ipynb`) from the repository root:

```bash
./DSA/scripts/refresh_java_notebooks.py
```

If `./…` fails with “permission denied”, run once from the repo root: `chmod +x DSA/scripts/refresh_java_notebooks.py`.

Re-run after you change the inputs the refresh script uses or adjust how notebooks are emitted (see the script docstring).

Hub overview: [../README.md](../README.md).
