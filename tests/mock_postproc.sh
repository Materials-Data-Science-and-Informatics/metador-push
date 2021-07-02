#!/bin/bash
# first argument: endpoint, second argument: path
# sends POST request to endpoint to notify about dataset
curl -X POST \
    -H "Content-Type: application/json" \
    -d "{\"event\": \"new_dataset\", \"location\": \"$2\"}" $1
