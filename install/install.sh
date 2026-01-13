#!/usr/bin/env bash

set -e

REPO_URL="https://github.com/prankapple/ThreadCrawl.git"
DIR_NAME="ThreadCrawl"

echo "🔽 Cloning ThreadCrawl..."
if [ -d "$DIR_NAME" ]; then
    echo "⚠️ Directory '$DIR_NAME' already exists. Skipping clone."
else
    git clone "$REPO_URL"
fi

cd "$DIR_NAME"

echo "🐍 Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "✅ Installation complete!"
cd ThreadCrawl
echo "▶ Run with: python3 crawler.py"
