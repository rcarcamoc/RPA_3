"""
Test script for the new dashboard panel
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from ui.panels.dashboard_panel import DashboardPanel

def main():
    app = QApplication(sys.argv)
    
    # Create and show dashboard
    dashboard = DashboardPanel()
    dashboard.setWindowTitle("Test Dashboard")
    dashboard.resize(1200, 800)
    dashboard.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
