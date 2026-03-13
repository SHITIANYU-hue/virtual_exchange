#!/bin/bash
# Setup script for Virtual Exchange experiments

set -e  # Exit on error

echo "=========================================="
echo "Virtual Exchange Experiment Setup"
echo "=========================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Virtual Exchange is running
echo -e "\n${YELLOW}Checking Virtual Exchange...${NC}"
if curl -s http://localhost:8000/api/prices > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Virtual Exchange is running${NC}"
else
    echo -e "${RED}✗ Virtual Exchange is not running${NC}"
    echo "Please start it with: docker-compose up -d"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv_experiment" ]; then
    echo -e "\n${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv_experiment
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate and install dependencies
echo -e "\n${YELLOW}Installing Python dependencies...${NC}"
source venv_experiment/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements_experiment.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Check for API keys
echo -e "\n${YELLOW}Checking API keys...${NC}"
if [ -z "$ANTHROPIC_API_KEY" ] && [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}✗ No API key found${NC}"
    echo "Please set one of:"
    echo "  export ANTHROPIC_API_KEY='sk-ant-...'"
    echo "  export OPENAI_API_KEY='sk-...'"
    exit 1
fi

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo -e "${GREEN}✓ Anthropic API key found${NC}"
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "${GREEN}✓ OpenAI API key found${NC}"
fi

# Register agents if not already registered
echo -e "\n${YELLOW}Checking agent registration...${NC}"
if [ ! -f "agents/.agent_keys.json" ]; then
    echo "Registering agents..."
    python3 agents/run.py --setup
    echo -e "${GREEN}✓ Agents registered${NC}"
else
    echo -e "${GREEN}✓ Agents already registered${NC}"
fi

# Test run - single cycle
echo -e "\n${YELLOW}Running test cycle...${NC}"
python3 agents/run.py --agent GoldenWhale --action prompt > /tmp/test_prompt.txt
echo -e "${GREEN}✓ Test cycle successful${NC}"

echo -e "\n=========================================="
echo -e "${GREEN}Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "You can now run experiments:"
echo ""
echo "  Quick test (10 cycles):"
echo "    python3 run_experiment.py --cycles 10"
echo ""
echo "  Overnight run (50 cycles):"
echo "    nohup python3 run_experiment.py --cycles 50 > experiment.log 2>&1 &"
echo ""
echo "  Full experiment (100 cycles, all agents):"
echo "    python3 run_experiment.py --cycles 100 --agents all"
echo ""
