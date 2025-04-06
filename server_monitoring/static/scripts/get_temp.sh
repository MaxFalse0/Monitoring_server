#!/bin/bash

if command -v sensors >/dev/null 2>&1; then
    sensors | grep -m 1 -Eo '[+][0-9]+\.[0-9]' | tr -d '+' && exit 0
fi

echo "-1"
