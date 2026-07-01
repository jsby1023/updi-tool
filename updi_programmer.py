from pathlib import Path
import ctypes
import hashlib
import json
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import winreg


MCU = "m4809"
PROGRAMMER = "serialupdi"
EXPECTED_SIGNATURE = "1e9651"
DEFAULT_PORT = "COM11"
DEFAULT_BAUD = "115200"
BAUD_RATES = ("115200", "57600", "38400", "19200")
FUSE_NAMES = (
    ("fuse0", "WDTCFG"),
    ("fuse1", "BODCFG"),
    ("fuse2", "OSCCFG"),
    ("fuse5", "SYSCFG0"),
    ("fuse6", "SYSCFG1"),
    ("fuse7", "APPEND / CODESIZE"),
    ("fuse8", "BOOTEND / BOOTSIZE"),
    ("lock", "LOCKBIT"),
)
FUSE_MASKS = {
    "fuse0": 0xFF,
    "fuse1": 0xFF,
    "fuse2": 0x07,
    "fuse5": 0xED,
    "fuse6": 0x1F,
    "fuse7": 0xFF,
    "fuse8": 0xFF,
}

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR
AVRDUDE = BASE_DIR / "avrdude.exe"
AVRDUDE_CONF = BASE_DIR / "avrdude.conf"
STALE_RUNTIME_AGE_SECONDS = 60 * 60


def prepare_runtime_directory():
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return

    current_runtime = BASE_DIR.resolve()
    _set_hidden_attribute(current_runtime)
    stale_before = time.time() - STALE_RUNTIME_AGE_SECONDS

    for folder in APP_DIR.glob("_MEI*"):
        try:
            if not folder.is_dir() or folder.resolve() == current_runtime:
                continue
            if folder.stat().st_mtime > stale_before:
                continue
            shutil.rmtree(folder)
        except OSError:
            # Another instance or security software can keep runtime files locked.
            continue


def _set_hidden_attribute(folder):
    file_attribute_hidden = 0x02
    invalid_file_attributes = 0xFFFFFFFF

    try:
        attributes = ctypes.windll.kernel32.GetFileAttributesW(str(folder))
        if attributes == invalid_file_attributes:
            return
        ctypes.windll.kernel32.SetFileAttributesW(
            str(folder), attributes | file_attribute_hidden
        )
    except (AttributeError, OSError):
        pass


class UpdiProgrammerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("ATmega4809 UPDI Programmer")
        self.geometry("820x560")
        self.minsize(720, 480)

        self.hex_path = tk.StringVar()
        self.hex_hash = tk.StringVar(value="No HEX file selected")
        self.profile_path = tk.StringVar()
        self.profile_name = tk.StringVar(value="No production profile")
        self.port = tk.StringVar(value=DEFAULT_PORT)
        self.baud = tk.StringVar(value=DEFAULT_BAUD)
        self.verify_after_write = tk.BooleanVar(value=True)
        self.fuse_values = {}
        self.fuse_write_flags = {}
        self.status = tk.StringVar(value="Ready")
        self.production_result = tk.StringVar(value="READY")
        self.output_queue = queue.Queue()
        self.worker = None

        self._build_ui()
        self.after(80, self._drain_output_queue)

        if not AVRDUDE.exists():
            messagebox.showerror("Error", f"avrdude.exe not found:\n{AVRDUDE}")
        elif not AVRDUDE_CONF.exists():
            messagebox.showwarning("Warning", f"avrdude.conf not found:\n{AVRDUDE_CONF}")

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(root)
        notebook.grid(row=0, column=0, sticky="nsew")

        program_tab = ttk.Frame(notebook, padding=10)
        fuse_tab = ttk.Frame(notebook, padding=10)
        notebook.add(program_tab, text="Program")
        notebook.add(fuse_tab, text="Fuses")

        program_tab.columnconfigure(0, weight=1)
        program_tab.rowconfigure(2, weight=1)
        fuse_tab.columnconfigure(0, weight=1)
        fuse_tab.rowconfigure(1, weight=1)

        file_frame = ttk.LabelFrame(program_tab, text="Files", padding=10)
        file_frame.grid(row=0, column=0, sticky="ew")
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="HEX File").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.file_entry = ttk.Entry(file_frame, textvariable=self.hex_path)
        self.file_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Button(file_frame, text="Browse", command=self.select_hex_file).grid(row=0, column=2)

        ttk.Label(file_frame, text="SHA-256").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.hash_entry = ttk.Entry(file_frame, textvariable=self.hex_hash, state="readonly")
        self.hash_entry.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Label(file_frame, text="Profile").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        self.profile_entry = ttk.Entry(file_frame, textvariable=self.profile_path)
        self.profile_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=(8, 0))
        ttk.Button(file_frame, text="Browse", command=self.select_profile).grid(row=2, column=2, pady=(8, 0))

        ttk.Label(file_frame, textvariable=self.profile_name).grid(
            row=3, column=1, sticky="w", pady=(6, 0)
        )

        options = ttk.LabelFrame(program_tab, text="Connection", padding=10)
        options.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        for column in range(8):
            options.columnconfigure(column, weight=0)
        options.columnconfigure(7, weight=1)

        ttk.Label(options, text="Port").grid(row=0, column=0, sticky="w")
        self.port_combo = ttk.Combobox(options, textvariable=self.port, width=14)
        self.port_combo.grid(row=0, column=1, sticky="w", padx=(6, 6))
        ttk.Button(options, text="Refresh", command=self.refresh_ports).grid(row=0, column=2, sticky="w", padx=(0, 18))

        ttk.Label(options, text="Baud").grid(row=0, column=3, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.baud,
            values=BAUD_RATES,
            width=10,
            state="readonly",
        ).grid(row=0, column=4, sticky="w", padx=(6, 18))

        ttk.Checkbutton(
            options,
            text="Verify",
            variable=self.verify_after_write,
        ).grid(row=0, column=5, sticky="w", padx=(0, 14))



        actions = ttk.Frame(program_tab)
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)

        self.production_result_label = tk.Label(
            actions,
            textvariable=self.production_result,
            width=12,
            font=("Segoe UI", 11, "bold"),
            bg="#d9d9d9",
            fg="#202020",
            relief="solid",
            borderwidth=1,
        )
        self.production_result_label.grid(row=0, column=0, sticky="w")

        self.check_button = ttk.Button(actions, text="Check Connection", command=self.check_connection)
        self.check_button.grid(row=0, column=1, padx=(0, 8))

        self.erase_button = ttk.Button(actions, text="Chip Erase", command=self.chip_erase)
        self.erase_button.grid(row=0, column=2, padx=(0, 8))

        self.program_button = ttk.Button(actions, text="Program HEX", command=self.program_hex)
        self.program_button.grid(row=0, column=3, padx=(0, 8))

        self.production_button = ttk.Button(
            actions,
            text="Production Program",
            command=self.production_program,
        )
        self.production_button.grid(row=0, column=4)

        log_frame = ttk.LabelFrame(program_tab, text="Log", padding=10)
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = tk.Text(log_frame, wrap="word", height=18, state="disabled")
        self.log.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        self._build_fuse_tab(fuse_tab)

        status_bar = ttk.Label(root, textvariable=self.status, anchor="w")
        status_bar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.refresh_ports()

    def _build_fuse_tab(self, parent):
        help_text = (
            "Read fuses and lock bits first. Only checked rows are written. "
            "Use hex byte values like 0x00, 0x08, or FF."
        )
        ttk.Label(parent, text=help_text, anchor="w").grid(row=0, column=0, sticky="ew")

        table = ttk.LabelFrame(parent, text="Fuse / Lock Settings", padding=10)
        table.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        table.columnconfigure(2, weight=1)

        ttk.Label(table, text="Write").grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Label(table, text="Memory").grid(row=0, column=1, sticky="w", padx=(0, 18))
        ttk.Label(table, text="Name").grid(row=0, column=2, sticky="w", padx=(0, 18))
        ttk.Label(table, text="Value").grid(row=0, column=3, sticky="w")

        for row, (fuse, label) in enumerate(FUSE_NAMES, start=1):
            self.fuse_write_flags[fuse] = tk.BooleanVar(value=False)
            self.fuse_values[fuse] = tk.StringVar()

            ttk.Checkbutton(table, variable=self.fuse_write_flags[fuse]).grid(row=row, column=0, sticky="w")
            ttk.Label(table, text=fuse).grid(row=row, column=1, sticky="w", padx=(0, 18))
            ttk.Label(table, text=label).grid(row=row, column=2, sticky="w", padx=(0, 18))
            ttk.Entry(table, textvariable=self.fuse_values[fuse], width=10).grid(row=row, column=3, sticky="w")

        fuse_actions = ttk.Frame(parent)
        fuse_actions.grid(row=2, column=0, sticky="ew")
        fuse_actions.columnconfigure(0, weight=1)

        self.read_fuses_button = ttk.Button(fuse_actions, text="Read Fuses", command=self.read_fuses)
        self.read_fuses_button.grid(row=0, column=1, padx=(0, 8))

        self.write_fuses_button = ttk.Button(fuse_actions, text="Write Checked Fuses", command=self.write_checked_fuses)
        self.write_fuses_button.grid(row=0, column=2)

    def refresh_ports(self):
        ports = self._list_serial_ports()
        self.port_combo.configure(values=ports)
        if ports and self.port.get() not in ports:
            self.port.set(ports[0])

    def _list_serial_ports(self):
        ports = []
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as key:
                index = 0
                while True:
                    try:
                        _, value, _ = winreg.EnumValue(key, index)
                    except OSError:
                        break
                    ports.append(value)
                    index += 1
        except OSError:
            pass

        def port_number(port):
            try:
                return int(port.upper().replace("COM", ""))
            except ValueError:
                return 9999

        return sorted(set(ports), key=port_number)

    def select_hex_file(self):
        filename = filedialog.askopenfilename(
            title="Select HEX file",
            filetypes=(("Intel HEX files", "*.hex"), ("All files", "*.*")),
        )
        if filename:
            self.hex_path.set(filename)
            self._update_hex_hash(Path(filename))

    def select_profile(self):
        filename = filedialog.askopenfilename(
            title="Select production profile",
            filetypes=(("Production profiles", "*.json"), ("All files", "*.*")),
        )
        if not filename:
            return

        self.profile_path.set(filename)
        try:
            profile = self._load_profile()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.profile_name.set("Invalid production profile")
            messagebox.showerror("Profile Error", str(error))
            return

        self.profile_name.set(f"{profile['profile_name']}  |  device: {profile['device']}")
        for memory in self.fuse_values:
            self.fuse_write_flags[memory].set(False)

        for memory, value in profile["normalized_fuses"].items():
            self.fuse_values[memory].set(value)
            self.fuse_write_flags[memory].set(True)

        if profile["normalized_lock"] is not None:
            self.fuse_values["lock"].set(profile["normalized_lock"])
            self.fuse_write_flags["lock"].set(True)

        firmware_path = self._profile_firmware_path(profile)
        if firmware_path and firmware_path.exists():
            self.hex_path.set(str(firmware_path))
            self._update_hex_hash(firmware_path)

    def _update_hex_hash(self, file_path):
        try:
            digest = self._calculate_file_hash(file_path)
        except OSError as error:
            self.hex_hash.set(f"Hash error: {error}")
            return None

        self.hex_hash.set(digest)
        return digest

    def _calculate_file_hash(self, file_path):
        sha256 = hashlib.sha256()
        with Path(file_path).open("rb") as firmware_file:
            while chunk := firmware_file.read(1024 * 1024):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _load_profile(self):
        profile_path = Path(self.profile_path.get().strip())
        if not profile_path.is_file():
            raise ValueError("Select a valid production profile JSON file.")

        with profile_path.open("r", encoding="utf-8") as profile_file:
            profile = json.load(profile_file)

        if not isinstance(profile, dict):
            raise ValueError("The production profile root must be a JSON object.")

        profile_name = profile.get("profile_name")
        if not isinstance(profile_name, str) or not profile_name.strip():
            raise ValueError("profile_name is required.")

        if profile.get("device") != MCU:
            raise ValueError(f"Profile device must be {MCU}.")

        signature = str(profile.get("signature", "")).lower().replace("0x", "")
        signature = re.sub(r"[^0-9a-f]", "", signature)
        if signature != EXPECTED_SIGNATURE:
            raise ValueError(f"Profile signature must be {EXPECTED_SIGNATURE}.")

        for option in ("chip_erase", "verify_flash"):
            if not isinstance(profile.get(option), bool):
                raise ValueError(f"{option} must be true or false.")

        fuses = profile.get("fuses", {})
        if not isinstance(fuses, dict):
            raise ValueError("fuses must be a JSON object.")

        allowed_fuses = {name for name, _ in FUSE_NAMES if name != "lock"}
        unknown_fuses = set(fuses) - allowed_fuses
        if unknown_fuses:
            raise ValueError(f"Unsupported fuse names: {', '.join(sorted(unknown_fuses))}")

        normalized_fuses = {}
        for memory, raw_value in fuses.items():
            value = self._normalize_fuse_value(str(raw_value))
            if value is None:
                raise ValueError(f"Invalid value for {memory}: {raw_value}")
            value_number = int(value, 16)
            if value_number & ~FUSE_MASKS[memory]:
                raise ValueError(
                    f"{memory} value {value} sets reserved bits "
                    f"(allowed mask: 0x{FUSE_MASKS[memory]:02x})."
                )
            normalized_fuses[memory] = value

        normalized_lock = None
        if profile.get("lock") is not None:
            normalized_lock = self._normalize_fuse_value(str(profile["lock"]))
            if normalized_lock is None:
                raise ValueError(f"Invalid lock value: {profile['lock']}")

        firmware = profile.get("firmware")
        if not isinstance(firmware, dict):
            raise ValueError("firmware must be a JSON object.")
        if not isinstance(firmware.get("file"), str) or not firmware["file"].strip():
            raise ValueError("firmware.file is required.")

        sha256 = str(firmware.get("sha256", "")).lower()
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("firmware.sha256 must contain 64 hexadecimal characters.")

        profile["profile_path"] = profile_path.resolve()
        profile["profile_name"] = profile_name.strip()
        profile["normalized_fuses"] = normalized_fuses
        profile["normalized_lock"] = normalized_lock
        profile["firmware_sha256"] = sha256
        return profile

    def _profile_firmware_path(self, profile):
        firmware_file = Path(profile["firmware"]["file"])
        if firmware_file.is_absolute():
            return firmware_file.resolve()
        return (profile["profile_path"].parent / firmware_file).resolve()

    def check_connection(self):
        self._run_task("Checking connection", self._connection_commands())

    def program_hex(self):
        hex_file = Path(self.hex_path.get().strip())
        if not hex_file.exists():
            messagebox.showerror("Error", "Select a valid HEX file first.")
            return

        command = self._base_command(self.baud.get())
        if not self.verify_after_write.get():
            command.append("-V")
        command.extend(["-U", f"flash:w:{self._avrdude_file_path(hex_file)}:i"])

        self._run_task("Programming HEX", [command], success_text="Programming completed")

    def production_program(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Busy", "Another operation is already running.")
            return

        try:
            profile = self._load_profile()
            firmware_path = self._validate_production_firmware(profile)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self._set_production_result("FAIL")
            messagebox.showerror("Production Profile Error", str(error))
            return

        summary = (
            f"Profile: {profile['profile_name']}\n"
            f"Firmware: {firmware_path.name}\n"
            f"Fuses: {len(profile['normalized_fuses'])}\n"
            f"Lock bit: {profile['normalized_lock'] or 'unchanged'}\n\n"
            "Start production programming?"
        )
        if not messagebox.askyesno("Confirm Production Program", summary):
            return

        self._clear_log()
        self._set_busy(True)
        self._set_production_result("RUNNING")
        self.status.set("Production programming")
        baud_rate = self.baud.get()
        port = self.port.get().strip()
        self.worker = threading.Thread(
            target=self._run_production,
            args=(profile, firmware_path, baud_rate, port),
            daemon=True,
        )
        self.worker.start()

    def _validate_production_firmware(self, profile):
        configured_path = self._profile_firmware_path(profile)
        selected_path = Path(self.hex_path.get().strip()) if self.hex_path.get().strip() else configured_path
        selected_path = selected_path.resolve()

        if not selected_path.is_file():
            raise ValueError(f"Firmware file not found: {selected_path}")
        if selected_path.name.lower() != configured_path.name.lower():
            raise ValueError(
                f"Selected HEX must match profile firmware: {configured_path.name}"
            )

        digest = self._calculate_file_hash(selected_path)
        self.hex_hash.set(digest)
        if digest != profile["firmware_sha256"]:
            raise ValueError(
                "Firmware SHA-256 does not match the production profile.\n"
                f"Expected: {profile['firmware_sha256']}\n"
                f"Actual:   {digest}"
            )

        self.hex_path.set(str(selected_path))
        return selected_path

    def _run_production(self, profile, firmware_path, baud_rate, port):
        try:
            _, signature_output = self._production_stage(
                "1. Check device signature",
                self._base_command(baud_rate, port)
                + ["-n", "-v", "-U", "signature:r:-:h"],
            )
            normalized_signature = re.sub(r"[^0-9a-f]", "", signature_output.lower())
            if EXPECTED_SIGNATURE not in normalized_signature:
                raise RuntimeError("Device signature does not match ATmega4809")

            if profile["chip_erase"]:
                self._production_stage(
                    "2. Chip erase",
                    self._base_command(baud_rate, port) + ["-e"],
                )

            flash_command = self._base_command(baud_rate, port)
            if not profile["verify_flash"]:
                flash_command.append("-V")
            flash_command.extend(
                ["-U", f"flash:w:{self._avrdude_file_path(firmware_path)}:i"]
            )
            self._production_stage("3. Program flash", flash_command)

            for memory, expected_value in profile["normalized_fuses"].items():
                self._production_stage(
                    f"4. Write {memory}",
                    self._base_command(baud_rate, port)
                    + ["-U", f"{memory}:w:{expected_value}:m"],
                )
                _, output = self._production_stage(
                    f"5. Verify {memory}",
                    self._base_command(baud_rate, port)
                    + ["-n", "-U", f"{memory}:r:-:h"],
                )
                actual_value = self._extract_memory_value(output)
                if actual_value != expected_value:
                    raise RuntimeError(
                        f"{memory} verify failed: expected {expected_value}, got {actual_value or 'no value'}"
                    )
                self.output_queue.put(("fuse", f"{memory}={actual_value}"))

            lock_value = profile["normalized_lock"]
            if lock_value is not None:
                self._production_stage(
                    "6. Write lock bit (last)",
                    self._base_command(baud_rate, port)
                    + ["-U", f"lock:w:{lock_value}:m"],
                )
                _, output = self._production_stage(
                    "7. Verify lock bit",
                    self._base_command(baud_rate, port)
                    + ["-n", "-U", "lock:r:-:h"],
                )
                actual_value = self._extract_memory_value(output)
                if actual_value != lock_value:
                    raise RuntimeError(
                        f"lock verify failed: expected {lock_value}, got {actual_value or 'no value'}"
                    )
                self.output_queue.put(("fuse", f"lock={actual_value}"))

            self.output_queue.put(("production_success", "Production programming completed"))
        except (OSError, RuntimeError) as error:
            self.output_queue.put(("production_error", str(error)))

    def _production_stage(self, stage_name, command):
        self.output_queue.put(("status", stage_name))
        self.output_queue.put(("log", f"\n=== {stage_name} ===\n> {' '.join(command)}\n\n"))
        returncode, output = self._run_process_streaming(command)
        if returncode != 0:
            raise RuntimeError(f"{stage_name} failed (exit code {returncode})")
        return returncode, output

    def chip_erase(self):
        if not messagebox.askyesno(
            "Confirm Chip Erase",
            "Chip erase will erase the flash contents of the connected ATmega4809.\n\nContinue?",
        ):
            return

        command = self._base_command(self.baud.get()) + ["-e"]
        self._run_task("Chip erase", [command], success_text="Chip erase completed")

    def read_fuses(self):
        commands = [
            self._base_command(self.baud.get()) + ["-n", "-U", f"{fuse}:r:-:h"]
            for fuse, _ in FUSE_NAMES
        ]
        self._run_task("Reading fuses", commands, success_text="Fuse read completed")

    def write_checked_fuses(self):
        commands = []

        for fuse, _ in FUSE_NAMES:
            if not self.fuse_write_flags[fuse].get():
                continue

            value = self._normalize_fuse_value(self.fuse_values[fuse].get())
            if value is None:
                messagebox.showerror("Error", f"Invalid value for {fuse}. Use 0x00 to 0xFF.")
                return

            commands.append(self._base_command(self.baud.get()) + ["-U", f"{fuse}:w:{value}:m"])

        if not commands:
            messagebox.showinfo("Fuses", "Check at least one fuse row to write.")
            return

        if not messagebox.askyesno(
            "Confirm Fuse Write",
            "Fuse and lock-bit settings can change clock, reset, boot, brown-out, and read/write protection behavior.\n"
            "Write only if these values are intended for this board.\n\n"
            "Continue?",
        ):
            return

        self._run_task("Writing fuses", commands, success_text="Fuse write completed")

    def _normalize_fuse_value(self, value):
        value = value.strip().lower()
        if value.startswith("0x"):
            value = value[2:]
        if len(value) == 0 or len(value) > 2:
            return None
        try:
            number = int(value, 16)
        except ValueError:
            return None
        if not 0 <= number <= 0xFF:
            return None
        return f"0x{number:02x}"

    def _avrdude_file_path(self, path):
        path = path.resolve()
        try:
            return str(path.relative_to(BASE_DIR))
        except ValueError:
            return str(path)

    def _connection_commands(self):
        selected = self.baud.get()
        baud_rates = [selected] + [rate for rate in BAUD_RATES if rate != selected]
        return [
            self._base_command(baud_rate) + ["-n", "-v", "-U", "signature:r:-:h"]
            for baud_rate in baud_rates
        ]

    def _base_command(self, baud_rate, port=None):
        command = [
            str(AVRDUDE),
            "-p",
            MCU,
            "-c",
            PROGRAMMER,
            "-P",
            port if port is not None else self.port.get().strip(),
            "-b",
            baud_rate,
        ]
        if AVRDUDE_CONF.exists():
            command[1:1] = ["-C", str(AVRDUDE_CONF)]
        return command

    def _run_task(self, title, commands, success_text=None):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Busy", "Another operation is already running.")
            return

        if not AVRDUDE.exists():
            messagebox.showerror("Error", f"avrdude.exe not found:\n{AVRDUDE}")
            return

        self._clear_log()
        self._set_busy(True)
        self.status.set(title)

        self.worker = threading.Thread(
            target=self._run_commands,
            args=(commands, success_text or f"{title} completed"),
            daemon=True,
        )
        self.worker.start()

    def _run_commands(self, commands, success_text):
        last_output = ""
        saw_failure = False
        needs_signature = any("signature:r:-:h" in command for command in commands)

        for command in commands:
            self.output_queue.put(("log", f"> {' '.join(command)}\n\n"))
            returncode, output = self._run_process_streaming(command)
            last_output = output

            normalized = output.replace(" ", "").replace("\n", "").lower()
            if returncode == 0:
                if "signature:r:-:h" in command:
                    if EXPECTED_SIGNATURE in normalized:
                        self.output_queue.put(("success", "Connection OK: ATmega4809 detected"))
                        return
                    continue
                self._queue_fuse_value(command, output)
                continue

            saw_failure = True
            lower_output = output.lower()
            if "cannot open port" in lower_output or "unable to open port" in lower_output:
                self.output_queue.put(("error", f"Cannot open {self.port.get().strip()}"))
                return

        if "updi link initialization failed" in last_output.lower():
            self.output_queue.put(("error", "COM port opened, but UPDI did not respond"))
        elif needs_signature:
            self.output_queue.put(("error", "ATmega4809 signature was not found"))
        elif saw_failure:
            self.output_queue.put(("error", "Operation failed"))
        else:
            self.output_queue.put(("success", success_text))

    def _run_process_streaming(self, command):
        startupinfo = None
        creationflags = 0
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        process = subprocess.Popen(
            command,
            cwd=APP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        output_parts = []
        pending = []

        while True:
            char = process.stdout.read(1)
            if char == "" and process.poll() is not None:
                break
            if char == "":
                continue

            output_parts.append(char)
            pending.append("\n" if char == "\r" else char)

            if char in ("\n", "\r") or len(pending) >= 80:
                self.output_queue.put(("log", "".join(pending)))
                pending.clear()

        if pending:
            self.output_queue.put(("log", "".join(pending)))

        return process.wait(), "".join(output_parts)

    def _queue_fuse_value(self, command, output):
        if not command:
            return

        memory_op = command[-1]
        if ":r:-:h" not in memory_op:
            return

        fuse = memory_op.split(":", 1)[0]
        if fuse not in self.fuse_values:
            return

        value = self._extract_memory_value(output)
        if value:
            self.output_queue.put(("fuse", f"{fuse}={value}"))

    def _extract_memory_value(self, output):
        matches = re.findall(r"(?m)^\s*(0x[0-9a-fA-F]{1,2})\s*$", output)
        if not matches:
            return None
        return self._normalize_fuse_value(matches[-1])

    def _drain_output_queue(self):
        try:
            while True:
                item_type, text = self.output_queue.get_nowait()
                if item_type == "log":
                    self._append_log(text)
                elif item_type == "success":
                    self.status.set(text)
                    self._append_log(text + "\n")
                    self._set_busy(False)
                    messagebox.showinfo("Success", text)
                elif item_type == "error":
                    self.status.set(text)
                    self._append_log(text + "\n")
                    self._set_busy(False)
                    messagebox.showerror("Error", text)
                elif item_type == "status":
                    self.status.set(text)
                elif item_type == "production_success":
                    self.status.set(text)
                    self._append_log(f"\nPASS: {text}\n")
                    self._set_production_result("PASS")
                    self._set_busy(False)
                    messagebox.showinfo("Production PASS", text)
                elif item_type == "production_error":
                    self.status.set(text)
                    self._append_log(f"\nFAIL: {text}\n")
                    self._set_production_result("FAIL")
                    self._set_busy(False)
                    messagebox.showerror("Production FAIL", text)
                elif item_type == "fuse":
                    fuse, value = text.split("=", 1)
                    if fuse in self.fuse_values:
                        self.fuse_values[fuse].set(value)
        except queue.Empty:
            pass

        self.after(80, self._drain_output_queue)

    def _append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert(tk.END, text)
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def _set_production_result(self, result):
        colors = {
            "READY": ("#d9d9d9", "#202020"),
            "RUNNING": ("#f4c542", "#202020"),
            "PASS": ("#16803a", "#ffffff"),
            "FAIL": ("#b42318", "#ffffff"),
        }
        background, foreground = colors[result]
        self.production_result.set(result)
        self.production_result_label.configure(bg=background, fg=foreground)

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.check_button.configure(state=state)
        self.erase_button.configure(state=state)
        self.program_button.configure(state=state)
        self.production_button.configure(state=state)
        self.read_fuses_button.configure(state=state)
        self.write_fuses_button.configure(state=state)


if __name__ == "__main__":
    prepare_runtime_directory()
    app = UpdiProgrammerApp()
    app.mainloop()
