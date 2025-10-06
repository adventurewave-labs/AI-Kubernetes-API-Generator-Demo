# 🚀 Quick Start Guide

## Get Running in 60 Seconds

### 1. Set Your OpenAI API Key
```bash
export OPENAI_API_KEY='your-openai-api-key-here'
```

### 2. Run the Demo
```bash
./run.sh demo
```

### 3. Interactive Mode
```bash
./run.sh interactive
```

## All Available Commands

```bash
# Run demo with examples
./run.sh demo

# Interactive chat mode
./run.sh interactive

# Run tests
./run.sh test

# Setup environment only
./run.sh setup

# Show help
./run.sh help
```

## Environment Setup

### Option 1: Export Variables (Temporary)
```bash
export OPENAI_API_KEY='your-key-here'
export AI_AGENT_DEBUG=true
./run.sh demo
```

### Option 2: .env File (Recommended)
```bash
cp .env.example .env
# Edit .env with your API key
./run.sh demo
```

### Option 3: Inline with Script
```bash
OPENAI_API_KEY='your-key-here' ./run.sh demo
```

## What You Need

- **Python 3.8+** (automatically detected)
- **OpenAI API Key** (required for AI functionality)
- **Git** (optional, for version control)

The script handles everything else automatically!