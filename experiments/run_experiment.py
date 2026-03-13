#!/usr/bin/env python3
"""
Automated Experiment Runner for Virtual Exchange
Runs multiple AI agents through trading cycles and logs all decisions.

Usage:
    python3 run_experiment.py --cycles 50 --agents GoldenWhale,HappyTrader,DiamondHands
    python3 run_experiment.py --config config.json
    python3 run_experiment.py --resume experiment_logs/20260313_064500
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Try to import LLM clients
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class ExperimentConfig:
    """Configuration for the experiment"""
    def __init__(
        self,
        agents: List[str],
        num_cycles: int,
        llm_provider: str = "anthropic",
        llm_model: str = "claude-sonnet-4-5-20250929",
        cycle_delay: int = 120,
        log_dir: Optional[str] = None,
        save_prompts: bool = True,
        save_responses: bool = True,
        verbose: bool = True
    ):
        self.agents = agents
        self.num_cycles = num_cycles
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.cycle_delay = cycle_delay
        self.save_prompts = save_prompts
        self.save_responses = save_responses
        self.verbose = verbose

        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_dir = Path(f"experiment_logs/{timestamp}")

        self.log_dir.mkdir(parents=True, exist_ok=True)

    def save(self):
        """Save config to log directory"""
        config_file = self.log_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump({
                'agents': self.agents,
                'num_cycles': self.num_cycles,
                'llm_provider': self.llm_provider,
                'llm_model': self.llm_model,
                'cycle_delay': self.cycle_delay,
                'save_prompts': self.save_prompts,
                'save_responses': self.save_responses,
            }, f, indent=2)

    @classmethod
    def load(cls, log_dir: str):
        """Load config from existing log directory"""
        config_file = Path(log_dir) / "config.json"
        with open(config_file) as f:
            data = json.load(f)
        return cls(log_dir=log_dir, **data)


class LLMClient:
    """Unified interface for different LLM providers"""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model

        if provider == "anthropic":
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            self.client = anthropic.Anthropic(api_key=api_key)

        elif provider == "openai":
            if not HAS_OPENAI:
                raise ImportError("openai package not installed. Run: pip install openai")
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.client = openai.OpenAI(api_key=api_key)

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_decision(self, prompt: str) -> Dict:
        """Get trading decision from LLM"""

        if self.provider == "anthropic":
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt + "\n\nIMPORTANT: Return ONLY the raw JSON object, no markdown code blocks, no explanation before or after."
                }]
            )
            content = message.content[0].text

        elif self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": prompt + "\n\nIMPORTANT: Return ONLY the raw JSON object, no markdown code blocks, no explanation before or after."
                }],
                max_tokens=2000
            )
            content = response.choices[0].message.content

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if not json_match:
            raise ValueError(f"No JSON found in LLM response: {content[:200]}")

        return json.loads(json_match.group(0))


class ExperimentRunner:
    """Main experiment runner"""

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.llm = LLMClient(config.llm_provider, config.llm_model)
        self.start_time = datetime.now()
        self.stats = {
            'total_trades': 0,
            'total_messages': 0,
            'errors': 0,
            'api_calls': 0
        }

        # Find Python in venv
        venv_python = Path("../venv_agent/bin/python3")
        if not venv_python.exists():
            venv_python = Path("venv_agent/bin/python3")
        if not venv_python.exists():
            venv_python = Path("python3")
        self.python_cmd = str(venv_python)

        # Create subdirectories
        (self.config.log_dir / "prompts").mkdir(exist_ok=True)
        (self.config.log_dir / "actions").mkdir(exist_ok=True)
        (self.config.log_dir / "status").mkdir(exist_ok=True)
        (self.config.log_dir / "errors").mkdir(exist_ok=True)

    def log(self, message: str, color: str = Colors.ENDC):
        """Print colored log message"""
        if self.config.verbose:
            print(f"{color}{message}{Colors.ENDC}")

    def get_agent_prompt(self, agent_name: str) -> str:
        """Get prompt for an agent"""
        result = subprocess.run(
            [self.python_cmd, "agents/run.py", "--agent", agent_name, "--action", "prompt"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(f"Failed to get prompt for {agent_name}: {result.stderr}")

        return result.stdout

    def execute_action(self, agent_name: str, action: Dict, cycle: int) -> bool:
        """Execute agent's trading action"""
        action_file = self.config.log_dir / "actions" / f"{agent_name}_cycle_{cycle}.json"

        with open(action_file, 'w') as f:
            json.dump(action, f, indent=2)

        result = subprocess.run(
            [self.python_cmd, "agents/run.py",
             "--agent", agent_name,
             "--action", "execute",
             "--action-file", str(action_file)],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            self.log(f"  {Colors.RED}✗ Execution failed: {result.stderr[:100]}{Colors.ENDC}", Colors.RED)
            return False

        # Count trades and messages
        num_trades = len(action.get('trades', []))
        num_messages = len(action.get('messages', []))
        self.stats['total_trades'] += num_trades
        self.stats['total_messages'] += num_messages

        return True

    def save_status(self, cycle: int):
        """Save current ecosystem status"""
        result = subprocess.run(
            [self.python_cmd, "agents/run.py", "--status"],
            capture_output=True,
            text=True,
            timeout=30
        )

        status_file = self.config.log_dir / "status" / f"cycle_{cycle}.txt"
        with open(status_file, 'w') as f:
            f.write(result.stdout)

    def run_cycle(self, cycle: int):
        """Run one complete cycle for all agents"""
        self.log(f"\n{Colors.BOLD}{'='*70}", Colors.CYAN)
        self.log(f"CYCLE {cycle}/{self.config.num_cycles}", Colors.CYAN)
        self.log(f"{'='*70}{Colors.ENDC}", Colors.CYAN)

        cycle_start = time.time()

        for agent_name in self.config.agents:
            self.log(f"\n{Colors.BLUE}[{agent_name}]{Colors.ENDC}")

            try:
                # 1. Get prompt
                self.log("  Fetching market state...", Colors.CYAN)
                prompt = self.get_agent_prompt(agent_name)

                if self.config.save_prompts:
                    prompt_file = self.config.log_dir / "prompts" / f"{agent_name}_cycle_{cycle}.txt"
                    with open(prompt_file, 'w') as f:
                        f.write(prompt)

                # 2. Get LLM decision
                self.log("  Calling LLM for decision...", Colors.CYAN)
                action = self.llm.get_decision(prompt)
                self.stats['api_calls'] += 1

                # Log reasoning
                reasoning = action.get('reasoning', 'N/A')
                self.log(f"  {Colors.YELLOW}Reasoning: {reasoning[:120]}...{Colors.ENDC}", Colors.YELLOW)

                # 3. Execute trades
                num_trades = len(action.get('trades', []))
                num_messages = len(action.get('messages', []))
                self.log(f"  Executing {num_trades} trades, {num_messages} messages...", Colors.CYAN)

                success = self.execute_action(agent_name, action, cycle)

                if success:
                    self.log(f"  {Colors.GREEN}✓ Success{Colors.ENDC}", Colors.GREEN)
                else:
                    self.stats['errors'] += 1

            except Exception as e:
                self.log(f"  {Colors.RED}✗ Error: {str(e)[:100]}{Colors.ENDC}", Colors.RED)
                self.stats['errors'] += 1

                # Save error details
                error_file = self.config.log_dir / "errors" / f"{agent_name}_cycle_{cycle}.txt"
                with open(error_file, 'w') as f:
                    f.write(f"Agent: {agent_name}\n")
                    f.write(f"Cycle: {cycle}\n")
                    f.write(f"Error: {str(e)}\n")
                    f.write(f"Traceback:\n")
                    import traceback
                    f.write(traceback.format_exc())

        # Save status snapshot
        self.log(f"\n{Colors.CYAN}Saving status snapshot...{Colors.ENDC}", Colors.CYAN)
        self.save_status(cycle)

        cycle_duration = time.time() - cycle_start
        self.log(f"{Colors.GREEN}Cycle completed in {cycle_duration:.1f}s{Colors.ENDC}", Colors.GREEN)

    def print_progress(self, cycle: int):
        """Print progress statistics"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        avg_cycle_time = elapsed / cycle if cycle > 0 else 0
        remaining_cycles = self.config.num_cycles - cycle
        eta_seconds = avg_cycle_time * remaining_cycles
        eta_hours = eta_seconds / 3600

        self.log(f"\n{Colors.HEADER}{'='*70}", Colors.HEADER)
        self.log(f"PROGRESS: {cycle}/{self.config.num_cycles} cycles ({cycle/self.config.num_cycles*100:.1f}%)", Colors.HEADER)
        self.log(f"Elapsed: {elapsed/60:.1f} min | ETA: {eta_hours:.1f} hours", Colors.HEADER)
        self.log(f"Total Trades: {self.stats['total_trades']} | Messages: {self.stats['total_messages']}", Colors.HEADER)
        self.log(f"API Calls: {self.stats['api_calls']} | Errors: {self.stats['errors']}", Colors.HEADER)
        self.log(f"{'='*70}{Colors.ENDC}", Colors.HEADER)

    def run(self, start_cycle: int = 1, skip_confirm: bool = False):
        """Run the complete experiment"""
        self.log(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}", Colors.HEADER)
        self.log(f"EXPERIMENT STARTING", Colors.HEADER)
        self.log(f"{'='*70}{Colors.ENDC}", Colors.HEADER)
        self.log(f"Cycles: {self.config.num_cycles}")
        self.log(f"Agents: {', '.join(self.config.agents)}")
        self.log(f"LLM: {self.config.llm_provider}/{self.config.llm_model}")
        self.log(f"Logs: {self.config.log_dir}")
        self.log(f"Cycle delay: {self.config.cycle_delay}s")

        # Estimate cost
        cost_per_call = 0.015 if self.config.llm_provider == "anthropic" else 0.03
        estimated_cost = self.config.num_cycles * len(self.config.agents) * cost_per_call
        self.log(f"Estimated API cost: ${estimated_cost:.2f}")

        # Save config
        self.config.save()
        self.log(f"{Colors.GREEN}Config saved to {self.config.log_dir / 'config.json'}{Colors.ENDC}")

        # Confirmation
        if start_cycle == 1 and not skip_confirm:
            response = input(f"\n{Colors.YELLOW}Press ENTER to start, or Ctrl+C to cancel...{Colors.ENDC}")

        try:
            for cycle in range(start_cycle, self.config.num_cycles + 1):
                self.run_cycle(cycle)

                # Print progress every 5 cycles
                if cycle % 5 == 0:
                    self.print_progress(cycle)

                # Wait for price update (except on last cycle)
                if cycle < self.config.num_cycles:
                    self.log(f"\n{Colors.CYAN}Waiting {self.config.cycle_delay}s for next price update...{Colors.ENDC}")
                    time.sleep(self.config.cycle_delay)

        except KeyboardInterrupt:
            self.log(f"\n{Colors.YELLOW}Experiment interrupted by user{Colors.ENDC}", Colors.YELLOW)
            self.log(f"Resume with: python3 run_experiment.py --resume {self.config.log_dir}")

        except Exception as e:
            self.log(f"\n{Colors.RED}Experiment failed: {e}{Colors.ENDC}", Colors.RED)
            import traceback
            traceback.print_exc()

        finally:
            self.print_final_report()

    def print_final_report(self):
        """Print final experiment report"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        self.log(f"\n{Colors.BOLD}{Colors.HEADER}{'='*70}", Colors.HEADER)
        self.log(f"EXPERIMENT COMPLETE", Colors.HEADER)
        self.log(f"{'='*70}{Colors.ENDC}", Colors.HEADER)
        self.log(f"Duration: {elapsed/3600:.2f} hours")
        self.log(f"Total Trades: {self.stats['total_trades']}")
        self.log(f"Total Messages: {self.stats['total_messages']}")
        self.log(f"API Calls: {self.stats['api_calls']}")
        self.log(f"Errors: {self.stats['errors']}")
        self.log(f"\n{Colors.GREEN}Results saved to: {self.config.log_dir}{Colors.ENDC}")
        self.log(f"\nNext steps:")
        self.log(f"  1. Analyze logs: python3 analyze_results.py {self.config.log_dir}")
        self.log(f"  2. View status: cat {self.config.log_dir}/status/cycle_*.txt")
        self.log(f"  3. Check messages: curl http://localhost:8000/api/messages/history")


def main():
    parser = argparse.ArgumentParser(description="Run Virtual Exchange Agent Experiment")

    parser.add_argument(
        "--cycles",
        type=int,
        default=50,
        help="Number of cycles to run (default: 50)"
    )

    parser.add_argument(
        "--agents",
        type=str,
        default="GoldenWhale,CryptoGuru,HappyTrader,DiamondHands,LeverageKing",
        help="Comma-separated list of agents (default: 5 key agents)"
    )

    parser.add_argument(
        "--llm-provider",
        choices=["anthropic", "openai"],
        default="anthropic",
        help="LLM provider (default: anthropic)"
    )

    parser.add_argument(
        "--llm-model",
        type=str,
        default="claude-sonnet-4-5-20250929",
        help="LLM model name"
    )

    parser.add_argument(
        "--delay",
        type=int,
        default=120,
        help="Delay between cycles in seconds (default: 120)"
    )

    parser.add_argument(
        "--resume",
        type=str,
        help="Resume from existing log directory"
    )

    parser.add_argument(
        "--config",
        type=str,
        help="Load config from JSON file"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce output verbosity"
    )

    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    # Load or create config
    if args.resume:
        config = ExperimentConfig.load(args.resume)
        # Find last completed cycle
        status_files = list(Path(args.resume).glob("status/cycle_*.txt"))
        start_cycle = len(status_files) + 1
        print(f"Resuming from cycle {start_cycle}")
    elif args.config:
        with open(args.config) as f:
            config_data = json.load(f)
        config = ExperimentConfig(**config_data)
        start_cycle = 1
    else:
        agents = args.agents.split(',')
        config = ExperimentConfig(
            agents=agents,
            num_cycles=args.cycles,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model,
            cycle_delay=args.delay,
            verbose=not args.quiet
        )
        start_cycle = 1

    # Run experiment
    runner = ExperimentRunner(config)
    runner.run(start_cycle=start_cycle, skip_confirm=args.yes)


if __name__ == "__main__":
    main()
