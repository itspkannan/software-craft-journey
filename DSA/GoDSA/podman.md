# Podman setup — Go Jupyter

Jupyter Lab runs in Podman with the **gophernotes** kernel, using the same VM as other projects (`course-vm` in the Makefile).

## Requirements

- Podman with `podman-compose`
- macOS or Linux

## First-time setup

```bash
cd DSA/GoDSA

make vm-start
make build
make start
```

Lab URL: **http://localhost:8890/lab**

## Daily usage

```bash
cd DSA/GoDSA
make vm-start
make start

# When done
make stop
make vm-stop
```

## Commands

| Command | Description |
|---------|-------------|
| `make vm-start` | Start the Podman machine |
| `make vm-stop` | Stop the Podman machine |
| `make vm-status` | Podman machine / connection status |
| `make build` | Build the image |
| `make start` | Start Jupyter Lab |
| `make stop` | Stop Jupyter Lab |
| `make logs` | Follow logs |
| `make status` | Container + quick health check |
| `make url` | Print Lab URL |
| `make clean` | Remove containers and named volumes |

## Troubleshooting

**Build logs: “SHELL / HEALTHCHECK is not supported for OCI image format”:** The Jupyter base image uses Dockerfile instructions that OCI manifests omit. `make build` sets `BUILDAH_FORMAT=docker` so Podman uses the Docker image schema and those warnings go away. If you run `podman-compose build` by hand, use the same prefix: `BUILDAH_FORMAT=docker podman-compose build`.

**Kernel “Go” missing:** `make clean && make build && make start`.

**Port in use:** Change `8890:8888` in `docker-compose.yml` and `LAB_PORT` in the `Makefile`.

**VM not running:** `make vm-status` then `make vm-start`.
