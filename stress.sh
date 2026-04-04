#!/usr/bin/env bash
for i in $(seq $(nproc)); do
  while true; do :; done &
done
