
from pywinauto import Desktop
import json

def get_windows():
    windows = []
    for win in Desktop(backend="uia").windows():
        try:
            title = win.window_text()
            if title:
                windows.append(title)
        except:
            pass
    return windows

if __name__ == "__main__":
    wins = get_windows()
    print(json.dumps(wins, indent=2))
