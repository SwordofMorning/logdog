"""
Watchdog Configuration Management with State Machine Support
"""
import os
import re
import json
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime

# Import state machine components
from state_machine import WatchdogStateMachine, WatchdogState, WatchdogTransition


class WatchdogRule:
    """Legacy single watchdog rule for backward compatibility"""
    
    def __init__(self, name: str, start_node: str, timeout_ms: int, end_node: str, description: str = ""):
        self.name = name
        self.start_node = start_node
        self.timeout_ms = timeout_ms
        self.end_node = end_node
        self.description = description
        self.last_start_time: Optional[datetime] = None
        self.is_active = False
    
    def __str__(self):
        return f"WatchdogRule({self.name}: {self.start_node} -> {self.end_node}, {self.timeout_ms}ms)"


class WatchdogConfig:
    """Enhanced watchdog configuration manager with state machine support"""
    
    def __init__(self):
        # Legacy rules for backward compatibility
        self.rules: Dict[str, WatchdogRule] = {}
        
        # New state machine for complex rules
        self.state_machine = WatchdogStateMachine()
        
        self.log_patterns = {
            'node_start': r'\[.*?\]\[.*?\]\[.*?\]\[.*?\]\[.*?\]\[.*?\] \[node_name=(.*?)\]',
            'node_complete': r'\[.*?\]\[.*?\]\[.*?\]\[.*?\]\[.*?\]\[.*?\] \[node_name=(.*?)\].*complete',
        }
        
        # External notification config
        self.bot_token = None
        self.chat_id = None
        self.webhook_key = None
        self.default_ext_notify = None
        
        # Monitoring settings
        self.log_file_path = None
        self.monitor_interval = 1.0
        self.enable_stdout_capture = False
        
    def load_config(self, config_path: str) -> bool:
        """Load watchdog configuration from file"""
        if not os.path.exists(config_path):
            print(f"Watchdog config file not found: {config_path}")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                current_section = None
                
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Section headers
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1].lower()
                        continue
                    
                    # Key-value pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        if current_section == 'notification':
                            self._parse_notification_config(key, value)
                        elif current_section == 'monitoring':
                            self._parse_monitoring_config(key, value)
                        elif current_section == 'rules':
                            self._parse_rule_config(key, value, line_num)
                        elif current_section == 'states':
                            self._parse_state_config(key, value, line_num)
            
            print(f"Loaded {len(self.rules)} legacy rules and {len(self.state_machine.states)} state machine rules")
            
            for rule_name, rule in self.rules.items():
                print(f"  Legacy - {rule}")
            
            for state_name, state in self.state_machine.states.items():
                print(f"  State - {state_name}: {state.start_node} -> {len(state.transitions)} transitions")
            
            return True
            
        except Exception as e:
            print(f"Failed to load watchdog config: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_notification_config(self, key: str, value: str):
        """Parse notification configuration"""
        if key == 'Bot_Token':
            self.bot_token = value if value else None
        elif key == 'Chat_ID':
            self.chat_id = value if value else None
        elif key == 'Webhook_Key':
            self.webhook_key = value if value else None
        elif key == 'Default_ExtNotify':
            self.default_ext_notify = value.lower() if value else None
    
    def _parse_monitoring_config(self, key: str, value: str):
        """Parse monitoring configuration"""
        if key == 'Log_File_Path':
            self.log_file_path = value if value else None
        elif key == 'Monitor_Interval':
            try:
                self.monitor_interval = float(value)
                if self.monitor_interval <= 0:
                    self.monitor_interval = 1.0
            except ValueError:
                print(f"Invalid Monitor_Interval: {value}, using default 1.0")
        elif key == 'Enable_Stdout_Capture':
            self.enable_stdout_capture = value.lower() in ['true', '1', 'yes', 'on']
    
    def _parse_rule_config(self, key: str, value: str, line_num: int):
        """Parse legacy watchdog rule configuration"""
        # Format: RuleName={StartNode, TimeoutMS, EndNode, Description}
        try:
            # Remove curly braces
            if value.startswith('{') and value.endswith('}'):
                value = value[1:-1]
            
            # Split by comma
            parts = [part.strip() for part in value.split(',')]
            
            if len(parts) < 3:
                print(f"Warning: Invalid rule format at line {line_num}: {key}={value}")
                return
            
            start_node = parts[0]
            timeout_ms = int(parts[1])
            end_node = parts[2]
            description = parts[3] if len(parts) > 3 else ""
            
            rule = WatchdogRule(key, start_node, timeout_ms, end_node, description)
            self.rules[key] = rule
            
        except (ValueError, IndexError) as e:
            print(f"Warning: Failed to parse rule at line {line_num}: {key}={value}, error: {e}")
    
    def _parse_state_config(self, key: str, value: str, line_num: int):
        """
        Parse new state machine rule configuration
        Format: RuleName={StartNode, TimeoutMS_1, EndNode_1, TimeoutMS_2, EndNode_2, ..., Description}
        """
        try:
            # Remove curly braces
            if value.startswith('{') and value.endswith('}'):
                value = value[1:-1]
            
            # Split by comma
            parts = [part.strip() for part in value.split(',')]
            
            if len(parts) < 3:
                print(f"Warning: Invalid state format at line {line_num}: {key}={value}")
                return
            
            start_node = parts[0]
            
            # Parse transitions: TimeoutMS_1, EndNode_1, TimeoutMS_2, EndNode_2, ...
            transitions = []
            i = 1
            while i < len(parts) - 1:  # -1 to leave room for description
                try:
                    timeout_ms = int(parts[i])
                    if i + 1 < len(parts):
                        end_node = parts[i + 1]
                        
                        # Check if next part is another timeout or description
                        if i + 2 < len(parts):
                            try:
                                # Try to parse next part as timeout
                                next_timeout = int(parts[i + 2])
                                # It's a timeout, so current end_node is valid
                                transitions.append(WatchdogTransition(end_node, timeout_ms, f"Transition to {end_node}"))
                                i += 2
                            except ValueError:
                                # Next part is not a timeout, so it's description
                                transitions.append(WatchdogTransition(end_node, timeout_ms, f"Final transition to {end_node}"))
                                break
                        else:
                            # Last transition
                            transitions.append(WatchdogTransition(end_node, timeout_ms, f"Final transition to {end_node}"))
                            break
                    else:
                        break
                except ValueError:
                    print(f"Warning: Invalid timeout value at line {line_num}: {parts[i]}")
                    break
            
            # Get description (last non-timeout part)
            description = ""
            if len(parts) > 2:
                # Find the description (should be the last part that's not part of timeout/node pairs)
                desc_start_idx = 1 + len(transitions) * 2
                if desc_start_idx < len(parts):
                    description = parts[desc_start_idx]
            
            if not transitions:
                print(f"Warning: No valid transitions found at line {line_num}: {key}={value}")
                return
            
            # Create state
            state = WatchdogState(
                name=key,
                start_node=start_node,
                transitions=transitions,
                description=description
            )
            
            self.state_machine.add_state(state)
            
        except (ValueError, IndexError) as e:
            print(f"Warning: Failed to parse state at line {line_num}: {key}={value}, error: {e}")
    
    def get_rule(self, name: str) -> Optional[WatchdogRule]:
        """Get legacy watchdog rule by name"""
        return self.rules.get(name)
    
    def get_state(self, name: str) -> Optional[WatchdogState]:
        """Get state machine rule by name"""
        return self.state_machine.states.get(name)
    
    def get_all_rules(self) -> List[WatchdogRule]:
        """Get all legacy watchdog rules"""
        return list(self.rules.values())
    
    def get_all_states(self) -> List[WatchdogState]:
        """Get all state machine rules"""
        return list(self.state_machine.states.values())
    
    def is_notification_configured(self) -> bool:
        """Check if notification is configured"""
        telegram_ok = self.bot_token and self.chat_id
        wechat_ok = self.webhook_key
        return telegram_ok or wechat_ok
    
    def get_available_notifiers(self) -> List[str]:
        """Get available notification platforms"""
        available = []
        if self.bot_token and self.chat_id:
            available.append('telegram')
        if self.webhook_key:
            available.append('wechat')
        return available


# Global config instance
watchdog_config = WatchdogConfig()

def load_watchdog_config(config_path: str) -> bool:
    """Load watchdog configuration"""
    return watchdog_config.load_config(config_path)

def get_watchdog_config() -> WatchdogConfig:
    """Get global watchdog configuration"""
    return watchdog_config