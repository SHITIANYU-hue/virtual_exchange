"""Auditor configuration."""
import os
from dataclasses import dataclass, field


@dataclass
class AuditorConfig:
    """Configuration for the Agent Auditor system.
    
    Attributes:
        block_threshold: ThreatSense score threshold to block a trade (0.0-1.0)
        flag_threshold: ThreatSense score threshold to flag a trade (0.0-1.0)
        mode: Enforcement mode - 'flag_only', 'block_and_flag', or 'log_only'
        llm_model: LLM model for intent analysis
        llm_timeout: Max seconds for LLM audit call
        cache_enabled: Whether to use the AuditCache
        cache_max_size: Maximum cache entries per scope
        rule_weight: Weight for rule-based score in ThreatSense
        stat_weight: Weight for statistical score in ThreatSense
        llm_weight: Weight for LLM score in ThreatSense
        wash_trade_window: Cycles to look back for wash trading
        pump_dump_window: Cycles for pump & dump detection
        front_run_window: Cycles for front-running detection
        enabled: Whether the auditor is active
    """
    block_threshold: float = 0.8
    flag_threshold: float = 0.4
    mode: str = 'block_and_flag'  # Updated to block_and_flag per user instruction
    llm_model: str = field(default_factory=lambda: os.environ.get('AUDITOR_LLM_MODEL', 'claude-haiku-4-5-20251001'))  # override via AUDITOR_LLM_MODEL
    llm_timeout: float = 10.0
    cache_enabled: bool = True
    cache_max_size: int = 1000
    rule_weight: float = 0.3
    stat_weight: float = 0.3
    llm_weight: float = 0.4
    wash_trade_window: int = 10
    pump_dump_window: int = 20
    front_run_window: int = 3
    enabled: bool = True
