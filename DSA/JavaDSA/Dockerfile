FROM jupyter/minimal-notebook:latest

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jdk-headless \
    curl \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Stable JAVA_HOME for amd64/arm64 (Debian OpenJDK layout)
RUN ln -sfn "$(dirname "$(dirname "$(readlink -f "$(which javac)")")")" /opt/java-home
ENV JAVA_HOME=/opt/java-home
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# IJava Jupyter kernel (Java cells in Lab)
ARG IJAVA_VERSION=1.3.0
RUN cd /tmp \
    && curl -fsSL -o ijava.zip "https://github.com/SpencerPark/IJava/releases/download/v${IJAVA_VERSION}/ijava-${IJAVA_VERSION}.zip" \
    && unzip -qo ijava.zip \
    && /opt/conda/bin/python3 install.py --sys-prefix \
    && rm -rf ijava.zip install.py java

USER ${NB_UID}

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir jupyterlab-git>=0.41.0

WORKDIR /home/jovyan

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser"]
