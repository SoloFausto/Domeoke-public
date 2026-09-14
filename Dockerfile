# syntax=docker/dockerfile:1.4
FROM ubuntu:24.04

# yt-dlp's YouTube challenge solver requires a supported JavaScript runtime.
COPY --from=denoland/deno:bin-2.5.6 /deno /usr/local/bin/deno

ENV DEBIAN_FRONTEND=noninteractive
# Must be chosen on the host; GPU hardware is not visible during docker build.
ARG DOMEOKE_BACKEND
ENV DOMEOKE_DEVICE=${DOMEOKE_BACKEND}
RUN case "${DOMEOKE_BACKEND}" in \
        cpu|cuda|rocm|xpu) ;; \
        *) echo 'Choose --build-arg DOMEOKE_BACKEND=cpu|cuda|rocm|xpu, or use python scripts/docker.py for host GPU detection.' >&2; exit 1 ;; \
    esac
ARG INSTALL_NEMO=0
ARG CHECKPOINT_FILENAME=melband_roformer_instvox_duality_v2.ckpt
ARG CHECKPOINT_URL=https://huggingface.co/pcunwa/Mel-Band-Roformer-InstVoc-Duality/resolve/main/melband_roformer_instvox_duality_v2.ckpt
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"
ENV NODE_PATH=/opt/lyrics_searcher/node_modules
ENV PIP_CONSTRAINT=/opt/venv/domeoke-constraints.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates wget curl git nodejs npm ffmpeg \
    libasound2-dev portaudio19-dev libportaudio2 libportaudiocpp0 \
    libffi-dev libssl-dev libbz2-dev libnuma1 libdrm2 libgomp1 \
    python3 python3-venv python3-dev build-essential software-properties-common && \
    rm -rf /var/lib/apt/lists/*

# User-mode compute libraries inside the image, NEVER host/kernel drivers.
# Intel's official Ubuntu PPA supplies the actual Level Zero GPU implementation,
# not only libze1 (the loader). Native Linux uses /dev/dri; WSL uses /dev/dxg.
RUN if [ "${DOMEOKE_BACKEND}" = "xpu" ]; then \
        add-apt-repository -y ppa:kobuk-team/intel-graphics && \
        apt-get update && \
        apt-get install -y --no-install-recommends libze1 libze-intel-gpu1 intel-opencl-icd && \
        rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app/DOMEOKE-BACKEND
COPY requirements.txt ./
COPY scripts/ ./scripts/
COPY lyrics_searcher/package*.json /opt/lyrics_searcher/

RUN python3 scripts/setup.py --backend "${DOMEOKE_BACKEND}" \
    --venv "${VIRTUAL_ENV}" --image-build --skip-assets

RUN cd /opt/lyrics_searcher && npm install

# Keep large model downloads cached across source edits.
RUN --mount=type=cache,target=/var/cache/domeoke/checkpoints \
    mkdir -p audio_processing/results processing/input_audio processing/output_audio \
        processing/sentence_level_srt processing/word_level_srt \
        processing/thumbnails processing/youtube_video && \
    if [ ! -s "/var/cache/domeoke/checkpoints/${CHECKPOINT_FILENAME}" ]; then \
        wget -O "/var/cache/domeoke/checkpoints/${CHECKPOINT_FILENAME}.download" "${CHECKPOINT_URL}" && \
        mv "/var/cache/domeoke/checkpoints/${CHECKPOINT_FILENAME}.download" "/var/cache/domeoke/checkpoints/${CHECKPOINT_FILENAME}"; \
    fi && \
    cp "/var/cache/domeoke/checkpoints/${CHECKPOINT_FILENAME}" "audio_processing/results/${CHECKPOINT_FILENAME}"

COPY . .

# NeMo's training/all extra is not part of the inference environment. Opt-in
# CUDA ASR only, resolved under the same backend constraints (conflicts fail).
RUN chmod +x ./scripts/run.sh && \
    if [ "${INSTALL_NEMO}" = "1" ]; then \
        test "${DOMEOKE_BACKEND}" = "cuda" || { echo 'NeMo installation is CUDA-only'; exit 1; }; \
        git clone -b main https://github.com/NVIDIA/NeMo NeMo && \
        python -m pip install 'nemo_toolkit[asr]'; \
    fi

EXPOSE 5000
CMD ["bash", "./scripts/run.sh"]
