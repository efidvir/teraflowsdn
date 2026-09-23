# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy common requirements and AI engine requirements
COPY common_requirements_py313.in /app/common_requirements.in
COPY src/tests/tools/simap_ai_engine/ai_engine/requirements.in /app/ai_requirements.in

# Install Python dependencies
RUN pip install --no-cache-dir pip-tools && \
    pip-compile --output-file=requirements.txt common_requirements.in ai_requirements.in && \
    pip install --no-cache-dir -r requirements.txt

# Copy minimal TFS common module (required for Settings, etc.)
COPY src/common /app/src/common

# Copy AI Engine module
COPY src/tests/tools/simap_ai_engine/ai_engine /app/ai_engine

# Set PYTHONPATH to include repo modules and the AI engine package
ENV PYTHONPATH=/app/src

# Expose default REST API port
EXPOSE 8080

# Set default environment variables (can be overridden at runtime)
ENV AI_ENGINE_REST_HOST=0.0.0.0
ENV AI_ENGINE_REST_PORT=8080
ENV SIMAP_DATASTORE_SCHEME=http
ENV LOG_LEVEL=INFO

# Note: SIMAP_DATASTORE_ADDRESS, SIMAP_DATASTORE_PORT, SIMAP_DATASTORE_USERNAME,
# and SIMAP_DATASTORE_PASSWORD should be provided at runtime via --env flags

# Run the AI Engine
CMD ["python", "-m", "ai_engine"]
