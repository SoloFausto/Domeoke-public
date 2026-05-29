FROM python:3.11-slim-bookworm

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ARG INSTALL_NEMO=0
ENV INSTALL_NEMO=${INSTALL_NEMO}
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV NODE_PATH=/opt/lyrics_searcher/node_modules

# Install required packages
RUN apt-get update && \
    apt-get install -y \
    ca-certificates \
    sudo \
    wget \
    curl \
    git \
    nodejs \
    npm \
    ffmpeg \
    libasound-dev \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    libffi-dev \
    libssl-dev \
    libbz2-dev \
    python3-dev \
    build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app/DOMEOKE-BACKEND

COPY requirements.txt triton_ops.py ./
COPY lyrics_searcher/package*.json /opt/lyrics_searcher/

# Install Python dependencies
RUN python -m venv "${VIRTUAL_ENV}" && \
    python -m pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install --no-deps git+https://github.com/openai/whisper && \
    for whisper_dir in "${VIRTUAL_ENV}"/lib/python*/site-packages/whisper "${VIRTUAL_ENV}"/lib64/python*/site-packages/whisper; do \
        if [ -d "$whisper_dir" ]; then \
            cp triton_ops.py "$whisper_dir/triton_ops.py"; \
        fi; \
    done

# Install Node dependencies
RUN cd /opt/lyrics_searcher && npm install

COPY . .

# Create directories and download model assets used by the application
RUN chmod +x ./scripts/run.sh && \
    mkdir -p audio_processing/results \
        processing/input_audio \
        processing/output_audio \
        processing/sentence_level_srt \
        processing/word_level_srt \
        processing/thumbnails \
        processing/youtube_video && \
    wget -O audio_processing/results/melband_roformer_instvox_duality_v2.ckpt \
        https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/melband_roformer_instvox_duality_v2.ckpt && \
    if [ "${INSTALL_NEMO}" = "1" ]; then \
        BRANCH="main"; \
        NEMO_DIR="NeMo"; \
        git clone -b "$BRANCH" https://github.com/NVIDIA/NeMo "$NEMO_DIR"; \
        python -m pip install "git+https://github.com/NVIDIA/NeMo.git@${BRANCH}#egg=nemo_toolkit[all]"; \
    fi

# Expose the necessary port
EXPOSE 5000

# Start the application
CMD ["bash", "./scripts/run.sh"]
