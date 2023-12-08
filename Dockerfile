# Build stage
FROM python:3.11.3-slim-buster AS build

# Copy only the requirements file first to leverage Docker cache if it hasn't changed
COPY requirements.txt /app/requirements.txt

# Install dependencies in a temporary container
RUN python -m pip install --upgrade pip && \
    pip3 --no-cache-dir install --user -r /app/requirements.txt

FROM python:3.11.3-slim-buster

# Copy installed dependencies from the build stage
COPY --from=build /root/.local /root/.local

# Copy the rest of the application files
COPY . /app

WORKDIR /app
# -u print打印出来
CMD ["/bin/bash", "-c", "set -e && python3 -u app.py"]