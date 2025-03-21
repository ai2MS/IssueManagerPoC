#!/bin/bash

# Function to display usage
usage() {
    echo "Usage: $0 [-t test_name] [-k]"
    exit 1
}

# Parse command line options
while getopts ":t:k" opt; do
  case $opt in
    t )
      test_name=$OPTARG
      ;;
    k )
      kill_docker=true
      ;;
    * )
      usage
      ;;
  esac
done

# Check if both -t and -k are provided
if [[ ! -z "$test_name" && ! -z "$kill_docker" ]]; then
    echo "Error: -t and -k options cannot be used together."
    usage
fi

# Execute the appropriate command based on the options
if [ ! -z "$test_name" ]; then
    echo "(re)starting docker compose"
    docker-compose up -d
    echo "Running python -m $test_name"
    python -m "$test_name"
elif [ ! -z "$kill_docker" ]; then
    echo "Running docker-compose down"
    docker-compose down
else
    docker-compose up -d
    docker-compose logs
fi
