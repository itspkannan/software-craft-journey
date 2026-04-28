# Podman Setup

Jupyter Lab runs in a Podman container using a shared VM (`course-vm`).

## Requirements

- Podman with podman-compose
- macOS or Linux

## First Time Setup

```bash
cd DSA/PythonDSA

# Start the Podman VM
make vm-start

# Build the Jupyter image
make build

# Start Jupyter Lab
make start
```

## Daily Usage

```bash
cd DSA/PythonDSA

# Start
make vm-start
make start

# When done
make stop
make vm-stop
```

## Commands

### VM Management

| Command | Description |
|---------|-------------|
| `make vm-start` | Start the Podman machine |
| `make vm-stop` | Stop the Podman machine |
| `make vm-status` | Show Podman machine status |

### Container Management

| Command | Description |
|---------|-------------|
| `make start` | Start Jupyter Lab |
| `make stop` | Stop Jupyter Lab |
| `make restart` | Restart Jupyter Lab |
| `make logs` | View container logs |
| `make ps` | Show running containers |
| `make status` | Check environment status |
| `make url` | Show Jupyter Lab URL |
| `make build` | Rebuild the image |
| `make clean` | Remove containers and volumes |

## Troubleshooting

**Container won't start:**
```bash
make vm-status    # Check if VM is running
make vm-start     # Start VM if needed
```

**Rebuild after changes:**
```bash
make stop
make build
make start
```

**Clean restart:**
```bash
make clean
make build
make start
```
