import tkinter as tk
import time

class CountdownTimer:
    """
    A simple countdown timer using Tkinter.
    Closes automatically after the specified duration.
    """
    def __init__(self, duration_seconds=10):
        self.root = tk.Tk()
        self.root.title("RPA Countdown")
        self.root.geometry("350x200")
        self.root.configure(bg='#1e1e2e')  # Elegant Dark Theme (Catppuccin Mocha)
        self.root.attributes("-topmost", True)  # Always stay on top
        self.root.overrideredirect(False) # Keep standard window decorations
        
        # Center the window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        # Title Label
        self.title_label = tk.Label(
            self.root, 
            text="ESPERA DE PROCESO", 
            font=("Segoe UI", 12, "bold"), 
            bg='#1e1e2e', 
            fg='#89b4fa'
        )
        self.title_label.pack(pady=(20, 0))

        # Main Countdown Label
        self.label = tk.Label(
            self.root, 
            text=self.format_time(duration_seconds), 
            font=("Segoe UI", 60, "bold"), 
            bg='#1e1e2e', 
            fg='#cdd6f4'
        )
        self.label.pack(expand=True)
        
        # Subtext
        self.sub_label = tk.Label(
            self.root, 
            text="Finalizará automáticamente", 
            font=("Segoe UI", 10), 
            bg='#1e1e2e', 
            fg='#a6adc8'
        )
        self.sub_label.pack(pady=(0, 20))

        self.remaining = duration_seconds
        self.update_timer()
        self.root.mainloop()

    def format_time(self, seconds):
        """Formats seconds into MM:SS."""
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def update_timer(self):
        """Updates the label every second."""
        if self.remaining > 0:
            self.remaining -= 1
            self.label.config(text=self.format_time(self.remaining))
            
            # Visual feedback as time runs out
            if self.remaining <= 10:
                self.label.config(fg='#f38ba8') # Soft Red
            elif self.remaining <= 30:
                self.label.config(fg='#fab387') # Soft Orange
                
            self.root.after(1000, self.update_timer)
        else:
            self.root.destroy()

if __name__ == "__main__":
    # Start a 2-minute countdown (120 seconds)
    CountdownTimer(120)
