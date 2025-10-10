#!/bin/bash

# Rebuild script for adminotaur agent
# This script automates building and deploying the adminotaur.agent binary

set -e  # Exit on error

echo "🔨 Adminotaur Rebuild Script"
echo "============================"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Define paths
AGENT_STORE_DIR="$HOME/.decyphertek-ai/store/agent/adminotaur"
OLD_BINARY="$AGENT_STORE_DIR/adminotaur.agent"
BUILD_SCRIPT="./build.sh"
# PyInstaller creates the binary in the parent directory
NEW_BINARY="../adminotaur.agent"

echo "📍 Working directory: $SCRIPT_DIR"
echo "📦 Agent store: $AGENT_STORE_DIR"
echo ""

# Step 1: Delete old binary if it exists
if [ -f "$OLD_BINARY" ]; then
    echo "🗑️  Step 1: Deleting old binary..."
    rm -f "$OLD_BINARY"
    echo "   ✅ Removed: $OLD_BINARY"
else
    echo "ℹ️  Step 1: No old binary found at $OLD_BINARY"
fi
echo ""

# Step 2: Run build.sh
if [ ! -f "$BUILD_SCRIPT" ]; then
    echo "❌ Error: build.sh not found in $SCRIPT_DIR"
    exit 1
fi

echo "🔧 Step 2: Running build.sh..."
chmod +x "$BUILD_SCRIPT"
bash "$BUILD_SCRIPT"

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi
echo "   ✅ Build successful"
echo ""

# Step 3: Verify new binary was created
if [ ! -f "$NEW_BINARY" ]; then
    echo "❌ Error: adminotaur.agent was not created by build.sh"
    exit 1
fi

# Step 4: Copy to agent store
echo "📋 Step 3: Copying binary to agent store..."
mkdir -p "$AGENT_STORE_DIR"
cp "$NEW_BINARY" "$AGENT_STORE_DIR/"

if [ $? -ne 0 ]; then
    echo "❌ Failed to copy binary to $AGENT_STORE_DIR"
    exit 1
fi

# Make sure the binary is executable
chmod +x "$AGENT_STORE_DIR/adminotaur.agent"

echo "   ✅ Copied to: $AGENT_STORE_DIR/adminotaur.agent"
echo ""

# Verify the copy
if [ -f "$AGENT_STORE_DIR/adminotaur.agent" ]; then
    BINARY_SIZE=$(stat -f%z "$AGENT_STORE_DIR/adminotaur.agent" 2>/dev/null || stat -c%s "$AGENT_STORE_DIR/adminotaur.agent" 2>/dev/null)
    echo "✅ Deployment successful!"
    echo "   Binary size: $BINARY_SIZE bytes"
    echo "   Location: $AGENT_STORE_DIR/adminotaur.agent"
else
    echo "❌ Verification failed: Binary not found at destination"
    exit 1
fi

echo ""
echo "🎉 Rebuild complete!"
echo ""
echo "The adminotaur agent has been rebuilt and deployed."
echo "You can now use it with @research mode and other features."
