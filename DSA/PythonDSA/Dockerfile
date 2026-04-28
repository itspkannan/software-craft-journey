FROM jupyter/scipy-notebook:latest

USER root

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

USER jovyan

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    pandas>=2.0.0 \
    'numpy<1.25,>=1.21' \
    scipy>=1.10.0 \
    matplotlib>=3.7.0 \
    seaborn>=0.12.0 \
    plotly>=5.13.0 \
    scikit-learn>=1.2.0 \
    statsmodels>=0.13.0 \
    jupyterlab-git>=0.41.0 \
    ipywidgets>=8.0.0 \
    tqdm>=4.65.0 \
    openpyxl>=3.10.0

RUN jupyter nbconvert --version

WORKDIR /home/jovyan

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
