# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy pyproject.toml and poetry.lock files to the container
COPY pyproject.toml poetry.lock ./

# Install the project dependencies
RUN poetry install --no-root

# Copy the rest of the application code to the container
COPY . .

# Specify the command to run your application
CMD ["poetry", "run", "python", "-m", "issue_evaluator"]
