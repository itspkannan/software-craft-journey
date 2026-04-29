FROM jupyter/minimal-notebook:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG GO_VERSION=1.23.4
# Pin to a published tag: https://github.com/gopherdata/gophernotes/tags
ARG GOPHERNOTES_VERSION=v0.7.5
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-${ARCH}.tar.gz" \
    | tar -C /usr/local -xz
ENV PATH="/usr/local/go/bin:${PATH}"

USER ${NB_UID}

ENV GOPATH=/home/jovyan/go
ENV PATH="${GOPATH}/bin:/usr/local/go/bin:${PATH}"

RUN mkdir -p "${GOPATH}/bin" \
    && go install "github.com/gopherdata/gophernotes@${GOPHERNOTES_VERSION}"

USER root

RUN mkdir -p /opt/conda/share/jupyter/kernels/gophernotes \
    && printf '%s\n' \
        '{"argv":["/home/jovyan/go/bin/gophernotes","{connection_file}"],"display_name":"Go","language":"go","name":"go"}' \
        > /opt/conda/share/jupyter/kernels/gophernotes/kernel.json \
    && chown -R ${NB_UID}:${NB_UID} /opt/conda/share/jupyter/kernels/gophernotes

USER ${NB_UID}

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir jupyterlab-git>=0.41.0

WORKDIR /home/jovyan

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"]
