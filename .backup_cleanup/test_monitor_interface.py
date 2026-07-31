# test_monitor_interface.py
from rpa_framework.ocr.actions import OCRActions
import inspect

def test_interface():
    sig = inspect.signature(OCRActions.capture_screenshot)
    if 'monitor_index' in sig.parameters:
        print("✅ capture_screenshot accepts monitor_index")
    else:
        print("❌ capture_screenshot missing monitor_index")
        
    sig2 = inspect.signature(OCRActions.capture_and_find)
    if 'monitor_index' in sig2.parameters:
        print("✅ capture_and_find accepts monitor_index")
    else:
        print("❌ capture_and_find missing monitor_index")

if __name__ == "__main__":
    test_interface()
