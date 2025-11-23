"""
MaaFramework Watchdog - Main Entry Point
Independent log-based watchdog for monitoring MaaFw agent execution
"""
import os
import sys
import time
import signal
import argparse
from datetime import datetime

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now import our modules
from config import load_watchdog_config, get_watchdog_config
from log_monitor import LogMonitor


class WatchdogService:
    """Main watchdog service"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or self._get_default_config_path()
        self.monitor: LogMonitor = None
        self.running = False
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _get_default_config_path(self) -> str:
        """Get default config file path"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(current_dir, 'watchdog.conf')
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.shutdown()
    
    def initialize(self) -> bool:
        """Initialize watchdog service"""
        print("Initializing MaaFramework Watchdog...")
        print(f"Config file: {self.config_path}")
        
        # Load configuration
        if not load_watchdog_config(self.config_path):
            print("Failed to load configuration")
            return False
        
        config = get_watchdog_config()
        
        # Validate configuration
        if not config.state_machine.states:
            print("No watchdog states configured")
            return False
        
        if not config.is_notification_configured():
            print("Warning: No notification platforms configured")
        
        # Create log monitor
        self.monitor = LogMonitor(config)
        
        print("Watchdog service initialized successfully")
        return True
    
    def start(self) -> bool:
        """Start watchdog service"""
        if not self.monitor:
            print("Watchdog not initialized")
            return False
        
        if self.running:
            print("Watchdog is already running")
            return False
        
        print("Starting watchdog service...")
        
        if not self.monitor.start_monitoring():
            print("Failed to start log monitoring")
            return False
        
        self.running = True
        print("Watchdog service started successfully")
        print(f"Monitoring started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Print status
        status = self.monitor.get_status()
        print(f"Status: {status}")
        
        return True
    
    def shutdown(self):
        """Shutdown watchdog service"""
        if not self.running:
            return
        
        print("Shutting down watchdog service...")
        
        if self.monitor:
            self.monitor.stop_monitoring()
        
        self.running = False
        print("Watchdog service stopped")
    
    def run(self):
        """Run watchdog service (blocking)"""
        if not self.start():
            return False
        
        try:
            # Main service loop
            while self.running:
                time.sleep(1)
                
                # Optional: Print periodic status
                # status = self.monitor.get_status()
                # print(f"[{datetime.now().strftime('%H:%M:%S')}] Active states: {status['active_state_rules']}")
        
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received")
        
        finally:
            self.shutdown()
        
        return True
    
    def print_status(self):
        """Print current status"""
        if not self.monitor:
            print("Watchdog not initialized")
            return
        
        status = self.monitor.get_detailed_status()
        config = get_watchdog_config()
        
        print("=== MaaFramework Watchdog Status ===")
        print(f"Running: {status['running']}")
        print(f"Config file: {self.config_path}")
        print(f"Log source: {status['log_source']}")
        print(f"Total states: {status['total_state_rules']}")
        print(f"Total entry nodes: {status['total_entry_nodes']}")
        print(f"Active states: {status['active_state_rules']}")
        
        if status['active_state_rule_names']:
            print("Active state names:")
            for state_name in status['active_state_rule_names']:
                state_status = status['state_details'].get(state_name)
                if state_status and state_status['is_active']:
                    elapsed = state_status.get('elapsed_ms', 0)
                    remaining = state_status.get('remaining_ms', 0)
                    current_target = state_status.get('current_target', 'N/A')
                    print(f"  - {state_name}: {elapsed:.1f}ms elapsed, {remaining}ms remaining, target: {current_target}")
        
        print(f"Notification available: {status['notification_available']}")
        if status['notification_available']:
            print(f"Available notifiers: {config.get_available_notifiers()}")
        
        print("\n=== State Configuration ===")
        for state_name, state in config.state_machine.states.items():
            transitions_info = []
            for transition in state.transitions:
                transitions_info.append(f"{transition.target_node}({transition.timeout_ms}ms)")
            transitions_str = " -> ".join(transitions_info)
            print(f"  - {state_name}: {state.start_node} -> {transitions_str}")
            if state.description:
                print(f"    Description: {state.description}")
        
        print("\n=== Entry Node Configuration ===")
        for entry_name, entry in config.entry_nodes.items():
            print(f"  - {entry_name}: {entry.node_name}")
            if entry.description:
                print(f"    Description: {entry.description}")
    
    def print_detailed_status(self):
        """Print detailed status including state machine details"""
        if not self.monitor:
            print("Watchdog not initialized")
            return
        
        status = self.monitor.get_detailed_status()
        config = get_watchdog_config()
        
        print("=== MaaFramework Watchdog Detailed Status ===")
        print(f"Running: {status['running']}")
        print(f"Config file: {self.config_path}")
        print(f"Log source: {status['log_source']}")
        
        print(f"\n=== State Machine Summary ===")
        print(f"Total states: {status['total_state_rules']}")
        print(f"Active states: {status['active_state_rules']}")
        print(f"Total entry nodes: {status['total_entry_nodes']}")
        
        print(f"\n=== Active States Details ===")
        if status['active_state_rule_names']:
            for state_name in status['active_state_rule_names']:
                state_detail = status['state_details'].get(state_name)
                if state_detail and state_detail['is_active']:
                    print(f"\n  State: {state_name}")
                    print(f"    Start Node: {state_detail['start_node']}")
                    print(f"    Description: {state_detail['description']}")
                    print(f"    Current Transition: {state_detail.get('current_transition_index', 0)}")
                    print(f"    Current Target: {state_detail.get('current_target', 'N/A')}")
                    print(f"    Elapsed Time: {state_detail.get('elapsed_ms', 0)}ms")
                    print(f"    Remaining Time: {state_detail.get('remaining_ms', 0)}ms")
                    print(f"    Transitions:")
                    for i, transition in enumerate(state_detail['transitions']):
                        marker = " -> " if i == state_detail.get('current_transition_index', 0) else "    "
                        print(f"      {marker}{transition['target_node']} ({transition['timeout_ms']}ms)")
        else:
            print("  No active states")
        
        print(f"\n=== All States Configuration ===")
        for state_name, state_detail in status['state_details'].items():
            active_marker = "[ACTIVE] " if state_detail['is_active'] else "[IDLE] "
            print(f"\n  {active_marker}{state_name}")
            print(f"    Start Node: {state_detail['start_node']}")
            print(f"    Description: {state_detail['description']}")
            print(f"    Transitions:")
            for transition in state_detail['transitions']:
                print(f"      -> {transition['target_node']} ({transition['timeout_ms']}ms)")
        
        print(f"\n=== Entry Nodes ===")
        for entry_name, entry_detail in status['entry_details'].items():
            print(f"  - {entry_name}: {entry_detail['node_name']}")
            if entry_detail['description']:
                print(f"    Description: {entry_detail['description']}")
        
        print(f"\n=== Notification Configuration ===")
        print(f"Notification available: {status['notification_available']}")
        if status['notification_available']:
            print(f"Available notifiers: {config.get_available_notifiers()}")
            print(f"Default platform: {config.default_ext_notify}")
        else:
            print("No notification platforms configured")


def print_logo():
    """
    Prints the Dinergate(Dandelion) (Girls' Frontline) ASCII art.
    """
    logo = r"""
              .=====================.
             /|                     |\
            | |  Dandelion Service  | |
            | |                     | |
            |  \___________________/  |
             \_______________________/
                     \      /
                      \    /
                 .-----`--'-----.
                / .------------. \
               / /    .----.    \ \
              | |    /  ()  \    | |
              | |   |   __   |   | |
               \ \   \      /   / /
                \ '------------' /
                 \              /
                 /`.__________.'\
                /   /        \   \
               ^   ^          ^   ^
    """
    print(logo)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='MaaFramework Watchdog Service')
    parser.add_argument('--config', '-c', type=str, help='Path to configuration file')
    parser.add_argument('--status', action='store_true', help='Show status and exit')
    parser.add_argument('--detailed-status', action='store_true', help='Show detailed status and exit')
    parser.add_argument('--daemon', '-d', action='store_true', help='Run as daemon (background)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Create service instance
    service = WatchdogService(args.config)
    
    # Initialize
    if not service.initialize():
        print("Failed to initialize watchdog service")
        sys.exit(1)
    
    # Handle status requests
    if args.detailed_status:
        service.print_detailed_status()
        sys.exit(0)
    
    if args.status:
        service.print_status()
        sys.exit(0)
    
    # Run service
    print("Starting MaaFramework Watchdog Service...")
    print("Press Ctrl+C to stop")
    print("Use --status for basic status, --detailed-status for full details")

    # Print Dandelion logo
    print_logo()
    
    success = service.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()