#!/bin/bash
if which curl > /dev/null 2>&1; then
    echo "curl is installed."
else
    echo "curl is not installed."
    apt-get install curl
fi

curl -fsSL https://ollama.com/install.sh | sh

ollama pull mistral-small