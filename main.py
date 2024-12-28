import cv2 as c2 
import time as t
import numpy as np
import ctypes as c
import win32api as wapi
import threading as th
import bettercam as bcam
from multiprocessing import Pipe as p, Process as proc
from ctypes import windll as wdl
import os
import json
import tkinter as tk
from tkinter import messagebox, ttk
import psutil  # For handling process priorities

# Constants
CONFIG_FILE = "config.json"
DEFAULT_HSV_RANGE = [(30, 125, 150), (30, 255, 255)]  # Fixed default HSV range

# Utility functions
def clear_terminal():
    os.system("cls" if os.name == "nt" else "clear")

def display_message(message):
    clear_terminal()
    print(f"\n{'='*50}\n{message}\n{'='*50}")

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

def load_config():
    try:
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load configuration: {str(e)}")
        return {}

def initialize_config():
    config = {}
    display_message("Creating New Configuration")
    config["fov"] = float(input("Enter FOV size: "))
    config["keybind"] = int(input("Enter keybind (hex): "), 16)
    config["shooting_rate"] = float(input("Enter shooting rate (ms): "))
    config["fps"] = float(input("Enter FPS: "))
    # Use the fixed default HSV range and don't allow changes
    config["hsv_range"] = DEFAULT_HSV_RANGE
    save_config(config)
    display_message("Configuration Saved!")
    return config

# Triggerbot logic
class TriggerBot:
    def __init__(self, config, pipe):
        user32 = wdl.user32
        self.width, self.height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        self.size = config["fov"]
        self.keybind = config["keybind"]
        self.shooting_rate = config["shooting_rate"]
        self.frame_duration = 1 / config["fps"]
        self.hsv_range = (
            np.array(config["hsv_range"][0], dtype=np.uint8),
            np.array(config["hsv_range"][1], dtype=np.uint8),
        )
        self.fov_region = (
            int(self.width / 2 - self.size),
            int(self.height / 2 - self.size),
            int(self.width / 2 + self.size),
            int(self.height / 2 + self.size),
        )
        self.camera = None
        self.pipe = pipe
        self.frame = None
        self.initialize_camera()

    def initialize_camera(self):
        if self.camera is not None:
            del self.camera
        try:
            self.camera = bcam.create(output_idx=0, region=self.fov_region)
        except Exception as e:
            print(f"Error initializing camera: {e}")
            self.camera = None

    def capture_frame(self):
        while True:
            if self.camera is None:
                self.initialize_camera()
            try:
                self.frame = self.camera.grab()
                t.sleep(self.frame_duration)
            except Exception as e:
                print(f"Error capturing frame: {e}")
                self.camera = None
                t.sleep(1)

    def detect_color(self):
        if self.frame is not None:
            hsv_frame = c2.cvtColor(self.frame, c2.COLOR_RGB2HSV)
            mask = c2.inRange(hsv_frame, self.hsv_range[0], self.hsv_range[1])
            return np.any(mask)
        return False

    def run(self):
        while True:
            if wapi.GetAsyncKeyState(self.keybind) < 0 and self.detect_color():
                self.pipe.send(b"\x01")
                t.sleep(self.shooting_rate / 1000)
            t.sleep(0.001)

# Keyboard event simulation
def keyboard_event(pipe):
    keybd_event = wdl.user32.keybd_event
    while True:
        try:
            key = pipe.recv()
            if key == b"\x01":
                keybd_event(0x4F, 0, 0, 0)  # O key press
                keybd_event(0x4F, 0, 2, 0)  # O key release
        except EOFError:
            break

# GUI Functions
class TriggerBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("TriggerBot Menu")
        self.root.geometry("700x500")
        self.root.configure(bg="#2E2E2E")
        self.root.resizable(False, False)

        # Password protection frame
        self.password_frame = tk.Frame(self.root, bg="#1c1c1c", padx=10, pady=10)
        self.password_frame.pack(pady=100)

        self.password_label = tk.Label(self.password_frame, text="Enter Password", font=("Arial", 18), fg="#E5E4E2", bg="#1c1c1c")
        self.password_label.grid(row=0, column=0)

        self.password_entry = tk.Entry(self.password_frame, show="*", font=("Arial", 18), fg="#E5E4E2", bg="#333333")
        self.password_entry.grid(row=0, column=1)

        self.password_button = tk.Button(self.password_frame, text="Enter", command=self.verify_password, bg="#4CAF50", fg="white", font=("Arial", 12), width=15, height=2)
        self.password_button.grid(row=1, columnspan=2, pady=20)

        # Main content will be hidden until password is correct
        self.main_frame = None

    def verify_password(self):
        password = self.password_entry.get()
        if password == "PLATINUM":
            self.password_frame.pack_forget()  # Hide password frame
            self.create_main_ui()
        else:
            messagebox.showerror("Error", "Invalid Password")

    def create_main_ui(self):
        # Main UI Layout after password is correct
        self.main_frame = tk.Frame(self.root, bg="#1c1c1c")
        self.main_frame.pack(fill="both", expand=True)

        # Tabs for main and beta sections
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True)

        # Main Tab
        self.main_tab = tk.Frame(self.notebook, bg="#2E2E2E")
        self.notebook.add(self.main_tab, text="Main")

        # Beta Tab
        self.beta_tab = tk.Frame(self.notebook, bg="#1E1E1E")
        self.notebook.add(self.beta_tab, text="Beta Features")

        # Title
        self.title_label = tk.Label(self.main_tab, text="TriggerBot v1.0", font=("Arial", 20, "bold"), fg="#E5E4E2", bg="#2E2E2E")
        self.title_label.pack(pady=10)

        # FOV Input
        self.fov_frame = tk.Frame(self.main_tab, bg="#2E2E2E")
        self.fov_frame.pack(pady=10)
        tk.Label(self.fov_frame, text="FOV Size:", font=("Arial", 12), fg="white", bg="#2E2E2E").grid(row=0, column=0, padx=5)
        self.fov_entry = tk.Entry(self.fov_frame, font=("Arial", 12))
        self.fov_entry.grid(row=0, column=1)

        # Keybind Input
        self.keybind_frame = tk.Frame(self.main_tab, bg="#2E2E2E")
        self.keybind_frame.pack(pady=10)
        tk.Label(self.keybind_frame, text="Keybind (Hex):", font=("Arial", 12), fg="white", bg="#2E2E2E").grid(row=0, column=0, padx=5)
        self.keybind_entry = tk.Entry(self.keybind_frame, font=("Arial", 12))
        self.keybind_entry.grid(row=0, column=1)

        # Shooting Rate Input
        self.rate_frame = tk.Frame(self.main_tab, bg="#2E2E2E")
        self.rate_frame.pack(pady=10)
        tk.Label(self.rate_frame, text="Shooting Rate (ms):", font=("Arial", 12), fg="white", bg="#2E2E2E").grid(row=0, column=0, padx=5)
        self.shooting_rate_entry = tk.Entry(self.rate_frame, font=("Arial", 12))
        self.shooting_rate_entry.grid(row=0, column=1)

        # FPS Input
        self.fps_frame = tk.Frame(self.main_tab, bg="#2E2E2E")
        self.fps_frame.pack(pady=10)
        tk.Label(self.fps_frame, text="FPS:", font=("Arial", 12), fg="white", bg="#2E2E2E").grid(row=0, column=0, padx=5)
        self.fps_entry = tk.Entry(self.fps_frame, font=("Arial", 12))
        self.fps_entry.grid(row=0, column=1)

        # Start Button
        self.start_button = tk.Button(self.main_tab, text="Start", command=self.start_triggerbot, bg="#4CAF50", fg="white", font=("Arial", 14), width=20, height=2)
        self.start_button.pack(pady=20)

        # Add content to Beta Features tab
        self.priority_label = tk.Label(self.beta_tab, text="Process Priority:", font=("Arial", 14), fg="white", bg="#1E1E1E")
        self.priority_label.pack(pady=20)

        self.priority_var = tk.StringVar(value="Normal")  # Default priority

        priority_options = ["Low", "Normal", "High"]
        self.priority_menu = tk.OptionMenu(self.beta_tab, self.priority_var, *priority_options)
        self.priority_menu.config(bg="#4CAF50", fg="white", font=("Arial", 12))
        self.priority_menu.pack(pady=10)

        self.set_priority_button = tk.Button(self.beta_tab, text="Set Priority", command=self.set_priority, bg="#4CAF50", fg="white", font=("Arial", 14))
        self.set_priority_button.pack(pady=20)

    def start_triggerbot(self):
        config = {
            "fov": float(self.fov_entry.get() or 200),
            "keybind": int(self.keybind_entry.get() or "0x01", 16),
            "shooting_rate": float(self.shooting_rate_entry.get() or 150),
            "fps": float(self.fps_entry.get() or 60),
            "hsv_range": DEFAULT_HSV_RANGE,
        }
        save_config(config)
        display_message("TriggerBot started")
        # Start triggerbot logic here
        self.pipe = p()
        triggerbot = TriggerBot(config, self.pipe)
        threading.Thread(target=triggerbot.run).start()

    def set_priority(self):
        priority = self.priority_var.get()
        pid = os.getpid()
        p = psutil.Process(pid)
        if priority == "Low":
            p.nice(psutil.IDLE_PRIORITY_CLASS)
        elif priority == "High":
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        else:
            p.nice(psutil.NORMAL_PRIORITY_CLASS)
        messagebox.showinfo("Priority", f"Priority set to {priority}")
        

def main():
    # Ensure all libraries are bundled during compilation.
    root = tk.Tk()
    gui = TriggerBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
