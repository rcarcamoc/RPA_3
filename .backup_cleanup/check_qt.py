

with open('check_qt_out.txt', 'w', encoding='utf-8') as f:
    try:
        import PyQt6.QtCharts
        f.write("Found PyQt6.QtCharts (plural)\n")
    except ImportError as e:
        f.write(f"No PyQt6.QtCharts: {e}\n")

    try:
        import PyQt6.QtChart
        f.write("Found PyQt6.QtChart (singular)\n")
    except ImportError as e:
        f.write(f"No PyQt6.QtChart: {e}\n")

    import site
    f.write(str(site.getsitepackages()) + "\n")
    import sys
    f.write(str(sys.path) + "\n")

