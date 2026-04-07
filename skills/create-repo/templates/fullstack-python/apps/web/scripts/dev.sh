#!/usr/bin/env bash
# Dev server with clean SIGINT handling.
trap 'exit 0' SIGINT SIGTERM
vite
