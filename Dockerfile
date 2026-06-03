FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.10 /usr/bin/python

COPY requirements.txt .

# Install Paddle GPU from Paddle's official index (matches CUDA 12.6 base image).
# Must happen before requirements.txt so paddleocr's transitive dep doesn't
# pull in CPU `paddlepaddle` from PyPI on top of it.
RUN pip install --no-cache-dir paddlepaddle-gpu==3.0.0 \
        -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ \
 && pip install --no-cache-dir -r requirements.txt

COPY src /app/src

EXPOSE 8000

ENV PYTHONPATH=/app

# Verify CUDA at runtime (when GPU driver is available), not at build time
CMD python -c "import paddle; assert paddle.device.is_compiled_with_cuda(), 'PaddlePaddle GPU not available'" \
 && uvicorn src.main:app --host 0.0.0.0 --port 8000
