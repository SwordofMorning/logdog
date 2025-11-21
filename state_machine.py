"""
Watchdog State Machine for complex rule management
"""
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import json
from dataclasses import dataclass, field


@dataclass
class WatchdogTransition:
    """Represents a transition from current state to next state"""
    target_node: str
    timeout_ms: int
    description: str = ""


@dataclass
class WatchdogState:
    """Represents a state in the watchdog state machine"""
    name: str
    start_node: str
    transitions: List[WatchdogTransition] = field(default_factory=list)
    description: str = ""
    is_active: bool = False
    last_activation_time: Optional[datetime] = None
    current_transition_index: int = 0


class WatchdogStateMachine:
    """State machine for managing complex watchdog rules"""
    
    def __init__(self):
        self.states: Dict[str, WatchdogState] = {}
        self.active_states: Dict[str, WatchdogState] = {}
        self.state_history: List[Tuple[str, str, datetime]] = []  # (rule_name, event, timestamp)
    
    def add_state(self, state: WatchdogState):
        """Add a new state to the state machine"""
        self.states[state.name] = state
    
    def activate_state(self, state_name: str, trigger_node: str) -> bool:
        """Activate a state when its start_node is triggered"""
        if state_name not in self.states:
            return False
        
        state = self.states[state_name]
        if trigger_node != state.start_node:
            return False
        
        current_time = datetime.now()
        
        # If already active, reset the timer
        if state.is_active:
            state.last_activation_time = current_time
            self.state_history.append((state_name, f"RESET by {trigger_node}", current_time))
            return True
        
        # Activate the state
        state.is_active = True
        state.last_activation_time = current_time
        state.current_transition_index = 0
        self.active_states[state_name] = state
        self.state_history.append((state_name, f"ACTIVATED by {trigger_node}", current_time))
        return True
    
    def check_transition(self, state_name: str, node_name: str) -> Optional[Tuple[bool, str]]:
        """
        Check if a node triggers a transition for an active state
        Returns: (is_completed, message)
        """
        if state_name not in self.active_states:
            return None
        
        state = self.active_states[state_name]
        if not state.transitions or state.current_transition_index >= len(state.transitions):
            return None
        
        current_transition = state.transitions[state.current_transition_index]
        
        if node_name == current_transition.target_node:
            current_time = datetime.now()
            
            # Move to next transition or complete the rule
            state.current_transition_index += 1
            
            if state.current_transition_index >= len(state.transitions):
                # All transitions completed
                self._deactivate_state(state_name, f"COMPLETED by {node_name}")
                return (True, f"Rule '{state_name}' completed successfully")
            else:
                # Move to next transition
                state.last_activation_time = current_time
                next_transition = state.transitions[state.current_transition_index]
                self.state_history.append((state_name, f"TRANSITION to {next_transition.target_node}", current_time))
                return (False, f"Rule '{state_name}' moved to next transition: {next_transition.target_node}")
        
        return None
    
    def check_timeouts(self) -> List[Tuple[str, WatchdogState, int]]:
        """Check for timeout conditions, returns list of (state_name, state, elapsed_ms)"""
        current_time = datetime.now()
        timeouts = []
        
        for state_name, state in list(self.active_states.items()):
            if not state.last_activation_time or state.current_transition_index >= len(state.transitions):
                continue
            
            current_transition = state.transitions[state.current_transition_index]
            elapsed_ms = (current_time - state.last_activation_time).total_seconds() * 1000
            
            if elapsed_ms > current_transition.timeout_ms:
                timeouts.append((state_name, state, int(elapsed_ms)))
                self._deactivate_state(state_name, f"TIMEOUT after {elapsed_ms:.1f}ms")
        
        return timeouts
    
    def _deactivate_state(self, state_name: str, reason: str):
        """Deactivate a state"""
        if state_name in self.active_states:
            state = self.active_states[state_name]
            state.is_active = False
            state.last_activation_time = None
            state.current_transition_index = 0
            del self.active_states[state_name]
            self.state_history.append((state_name, reason, datetime.now()))
    
    def get_active_states(self) -> Dict[str, WatchdogState]:
        """Get all currently active states"""
        return self.active_states.copy()
    
    def get_state_status(self, state_name: str) -> Optional[Dict]:
        """Get detailed status of a specific state"""
        if state_name not in self.states:
            return None
        
        state = self.states[state_name]
        status = {
            'name': state.name,
            'start_node': state.start_node,
            'description': state.description,
            'is_active': state.is_active,
            'transitions': [
                {
                    'target_node': t.target_node,
                    'timeout_ms': t.timeout_ms,
                    'description': t.description
                }
                for t in state.transitions
            ]
        }
        
        if state.is_active:
            status['current_transition_index'] = state.current_transition_index
            if state.current_transition_index < len(state.transitions):
                current_transition = state.transitions[state.current_transition_index]
                status['current_target'] = current_transition.target_node
                status['current_timeout'] = current_transition.timeout_ms
                
                if state.last_activation_time:
                    elapsed = (datetime.now() - state.last_activation_time).total_seconds() * 1000
                    status['elapsed_ms'] = int(elapsed)
                    status['remaining_ms'] = max(0, current_transition.timeout_ms - int(elapsed))
        
        return status