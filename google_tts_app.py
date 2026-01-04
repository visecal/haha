#!/usr/bin/env python3
"""
Google TTS Desktop Application
Using Google's Little Language Lessons (LLL) API
Supports text chunking for long texts and multiple voices/languages
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import base64
import threading
import os
import tempfile
import io
import json
from datetime import datetime
from typing import Optional, List, Tuple
import re

# Try to import optional dependencies
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("Warning: pydub not installed. Audio concatenation will use simple method.")

try:
    import pygame
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    print("Warning: pygame not installed. Playback will use system default player.")


# =============================================================================
# CONFIGURATION - Google LLL API
# =============================================================================

GOOGLE_TTS_API = "https://labs.google/lll/api/text-to-speech"

# Updated voice list - Chirp3-HD voices from Google
# Format: (voice_id, display_name, gender, description)
VOICES = [
    # Original voices
    ("Puck", "Puck", "Male", "Energetic and playful"),
    ("Charon", "Charon", "Male", "Deep and mysterious"),
    ("Kore", "Kore", "Female", "Warm and gentle"),
    ("Fenrir", "Fenrir", "Male", "Strong and commanding"),
    ("Aoede", "Aoede", "Female", "Musical and flowing"),
    ("Leda", "Leda", "Female", "Friendly and reassuring"),
    ("Orus", "Orus", "Male", "Clear and professional"),
    ("Zephyr", "Zephyr", "Neutral", "Soft and calm"),

    # New Chirp voices (2024-2025 updates)
    ("Achernar", "Achernar", "Male", "Confident narrator"),
    ("Autonoe", "Autonoe", "Female", "Sophisticated and elegant"),
    ("Callirrhoe", "Callirrhoe", "Female", "Expressive storyteller"),
    ("Despina", "Despina", "Female", "Bright and cheerful"),
    ("Erinome", "Erinome", "Female", "Calm and soothing"),
    ("Gacrux", "Gacrux", "Male", "Mature and wise"),
    ("Isonoe", "Isonoe", "Female", "Natural conversational"),
    ("Keid", "Keid", "Male", "Warm baritone"),
    ("Laomedeia", "Laomedeia", "Female", "Articulate and clear"),
    ("Pulcherrima", "Pulcherrima", "Female", "Rich and melodic"),
    ("Rasalas", "Rasalas", "Male", "Dynamic presenter"),
    ("Sadachbia", "Sadachbia", "Male", "Friendly guide"),
    ("Sadaltager", "Sadaltager", "Male", "Authoritative"),
    ("Schedar", "Schedar", "Female", "Professional announcer"),
    ("Sulafat", "Sulafat", "Female", "Gentle teacher"),
    ("Umbriel", "Umbriel", "Neutral", "Mysterious and intriguing"),
    ("Vindemiatrix", "Vindemiatrix", "Female", "Warm storyteller"),
    ("Alnilam", "Alnilam", "Male", "Bold and clear"),
    ("Algieba", "Algieba", "Male", "Smooth narrator"),
    ("Algenib", "Algenib", "Male", "Energetic host"),
]

# Supported languages with their codes
LANGUAGES = [
    ("en-US", "English (US)"),
    ("en-GB", "English (UK)"),
    ("en-AU", "English (Australia)"),
    ("en-IN", "English (India)"),
    ("vi-VN", "Vietnamese (Vietnam)"),
    ("es-ES", "Spanish (Spain)"),
    ("es-MX", "Spanish (Mexico)"),
    ("es-US", "Spanish (US)"),
    ("fr-FR", "French (France)"),
    ("fr-CA", "French (Canada)"),
    ("de-DE", "German (Germany)"),
    ("it-IT", "Italian (Italy)"),
    ("pt-BR", "Portuguese (Brazil)"),
    ("pt-PT", "Portuguese (Portugal)"),
    ("ja-JP", "Japanese (Japan)"),
    ("ko-KR", "Korean (Korea)"),
    ("zh-CN", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"),
    ("ru-RU", "Russian (Russia)"),
    ("ar-XA", "Arabic"),
    ("hi-IN", "Hindi (India)"),
    ("bn-IN", "Bengali (India)"),
    ("ta-IN", "Tamil (India)"),
    ("te-IN", "Telugu (India)"),
    ("th-TH", "Thai (Thailand)"),
    ("id-ID", "Indonesian"),
    ("ms-MY", "Malay (Malaysia)"),
    ("fil-PH", "Filipino (Philippines)"),
    ("nl-NL", "Dutch (Netherlands)"),
    ("pl-PL", "Polish (Poland)"),
    ("tr-TR", "Turkish (Turkey)"),
    ("uk-UA", "Ukrainian (Ukraine)"),
    ("cs-CZ", "Czech (Czech Republic)"),
    ("da-DK", "Danish (Denmark)"),
    ("fi-FI", "Finnish (Finland)"),
    ("el-GR", "Greek (Greece)"),
    ("he-IL", "Hebrew (Israel)"),
    ("hu-HU", "Hungarian (Hungary)"),
    ("nb-NO", "Norwegian (Norway)"),
    ("ro-RO", "Romanian (Romania)"),
    ("sk-SK", "Slovak (Slovakia)"),
    ("sv-SE", "Swedish (Sweden)"),
    ("bg-BG", "Bulgarian (Bulgaria)"),
    ("ca-ES", "Catalan (Spain)"),
    ("hr-HR", "Croatian (Croatia)"),
    ("lt-LT", "Lithuanian (Lithuania)"),
    ("lv-LV", "Latvian (Latvia)"),
    ("sl-SI", "Slovenian (Slovenia)"),
    ("sr-RS", "Serbian (Serbia)"),
    ("af-ZA", "Afrikaans (South Africa)"),
    ("sw-KE", "Swahili (Kenya)"),
]


# =============================================================================
# TTS ENGINE
# =============================================================================

class TTSEngine:
    """Handle TTS API calls and audio processing"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def generate_speech(self, text: str, language_code: str, voice_name: str) -> Optional[bytes]:
        """
        Generate speech from text using Google LLL API

        Args:
            text: Text to convert to speech
            language_code: Language code (e.g., 'en-US')
            voice_name: Voice name (e.g., 'Orus')

        Returns:
            MP3 audio bytes or None if failed
        """
        full_voice_name = f"{language_code}-Chirp3-HD-{voice_name}"

        payload = {
            "text": text,
            "languageCode": language_code,
            "voiceName": full_voice_name
        }

        try:
            response = self.session.post(
                GOOGLE_TTS_API,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            # Response is base64 encoded audio
            audio_base64 = response.json()
            if isinstance(audio_base64, str):
                audio_bytes = base64.b64decode(audio_base64)
                return audio_bytes
            else:
                print(f"Unexpected response format: {type(audio_base64)}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None
        except Exception as e:
            print(f"Error generating speech: {e}")
            return None

    def split_text_into_chunks(self, text: str, chunk_size: int = 500) -> List[str]:
        """
        Split text into chunks, trying to break at sentence boundaries

        Args:
            text: Text to split
            chunk_size: Maximum characters per chunk

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            # If single sentence is longer than chunk_size, split by words
            if len(sentence) > chunk_size:
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= chunk_size:
                        current_chunk += (" " if current_chunk else "") + word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = word
            else:
                if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                    current_chunk += (" " if current_chunk else "") + sentence
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def concatenate_audio(self, audio_chunks: List[bytes]) -> bytes:
        """
        Concatenate multiple audio chunks into one

        Args:
            audio_chunks: List of MP3 audio bytes

        Returns:
            Combined MP3 audio bytes
        """
        if len(audio_chunks) == 1:
            return audio_chunks[0]

        if PYDUB_AVAILABLE:
            # Use pydub for proper concatenation
            combined = AudioSegment.empty()
            for chunk in audio_chunks:
                segment = AudioSegment.from_mp3(io.BytesIO(chunk))
                combined += segment

            output = io.BytesIO()
            combined.export(output, format="mp3")
            return output.getvalue()
        else:
            # Simple concatenation (may have artifacts)
            return b''.join(audio_chunks)


# =============================================================================
# GUI APPLICATION
# =============================================================================

class TTSApplication:
    """Main TTS Desktop Application"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Google TTS Desktop - Chirp3-HD Voices")
        self.root.geometry("900x750")
        self.root.minsize(800, 650)

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Configure colors
        self.root.configure(bg='#f5f5f5')
        self.style.configure('TFrame', background='#f5f5f5')
        self.style.configure('TLabel', background='#f5f5f5', font=('Segoe UI', 10))
        self.style.configure('TButton', font=('Segoe UI', 10))
        self.style.configure('Header.TLabel', font=('Segoe UI', 14, 'bold'))
        self.style.configure('Subheader.TLabel', font=('Segoe UI', 11, 'bold'))

        # Initialize engine
        self.engine = TTSEngine()

        # State variables
        self.current_audio: Optional[bytes] = None
        self.is_generating = False
        self.temp_audio_file: Optional[str] = None

        # Build UI
        self._build_ui()

        # Bind cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Build the main UI"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(
            header_frame,
            text="Google TTS Desktop",
            style='Header.TLabel'
        ).pack(side=tk.LEFT)

        ttk.Label(
            header_frame,
            text="Powered by Google Chirp3-HD",
            foreground='#666'
        ).pack(side=tk.RIGHT)

        # Create notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Main TTS Tab
        tts_frame = ttk.Frame(notebook, padding="10")
        notebook.add(tts_frame, text="Text to Speech")

        # Settings Tab
        settings_frame = ttk.Frame(notebook, padding="10")
        notebook.add(settings_frame, text="Settings")

        self._build_tts_tab(tts_frame)
        self._build_settings_tab(settings_frame)

    def _build_tts_tab(self, parent):
        """Build the main TTS interface"""
        # Text input section
        text_frame = ttk.LabelFrame(parent, text="Text Input", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Text area with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=tk.BOTH, expand=True)

        self.text_input = tk.Text(
            text_container,
            wrap=tk.WORD,
            font=('Segoe UI', 11),
            height=10,
            padx=10,
            pady=10
        )
        scrollbar = ttk.Scrollbar(text_container, orient=tk.VERTICAL, command=self.text_input.yview)
        self.text_input.configure(yscrollcommand=scrollbar.set)

        self.text_input.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Character counter
        counter_frame = ttk.Frame(text_frame)
        counter_frame.pack(fill=tk.X, pady=(5, 0))

        self.char_count_label = ttk.Label(counter_frame, text="Characters: 0")
        self.char_count_label.pack(side=tk.LEFT)

        self.chunk_info_label = ttk.Label(counter_frame, text="", foreground='#666')
        self.chunk_info_label.pack(side=tk.RIGHT)

        # Bind text change event
        self.text_input.bind('<KeyRelease>', self._on_text_change)

        # Voice settings section
        settings_frame = ttk.LabelFrame(parent, text="Voice Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        # Grid layout for settings
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X)

        # Language selection
        ttk.Label(settings_grid, text="Language:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.language_var = tk.StringVar(value="en-US")
        self.language_combo = ttk.Combobox(
            settings_grid,
            textvariable=self.language_var,
            values=[f"{code} - {name}" for code, name in LANGUAGES],
            state='readonly',
            width=35
        )
        self.language_combo.current(0)
        self.language_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Voice selection
        ttk.Label(settings_grid, text="Voice:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.voice_var = tk.StringVar(value="Orus")
        self.voice_combo = ttk.Combobox(
            settings_grid,
            textvariable=self.voice_var,
            values=[f"{v[0]} ({v[2]}) - {v[3]}" for v in VOICES],
            state='readonly',
            width=35
        )
        self.voice_combo.current(6)  # Default to Orus
        self.voice_combo.grid(row=1, column=1, sticky=tk.W, pady=5)

        # Chunk size
        ttk.Label(settings_grid, text="Chunk Size:").grid(row=0, column=2, sticky=tk.W, padx=(30, 10))
        self.chunk_size_var = tk.StringVar(value="500")
        chunk_spinbox = ttk.Spinbox(
            settings_grid,
            from_=100,
            to=2000,
            increment=50,
            textvariable=self.chunk_size_var,
            width=10
        )
        chunk_spinbox.grid(row=0, column=3, sticky=tk.W, pady=5)
        ttk.Label(settings_grid, text="chars", foreground='#666').grid(row=0, column=4, sticky=tk.W, padx=(5, 0))

        # Progress section
        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))

        self.status_label = ttk.Label(progress_frame, text="Ready", foreground='#666')
        self.status_label.pack(side=tk.LEFT)

        # Action buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X)

        self.generate_btn = ttk.Button(
            button_frame,
            text="Generate Speech",
            command=self._on_generate
        )
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.play_btn = ttk.Button(
            button_frame,
            text="Play",
            command=self._on_play,
            state=tk.DISABLED
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.stop_btn = ttk.Button(
            button_frame,
            text="Stop",
            command=self._on_stop,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.save_btn = ttk.Button(
            button_frame,
            text="Save MP3",
            command=self._on_save,
            state=tk.DISABLED
        )
        self.save_btn.pack(side=tk.LEFT)

        # Clear button on right
        ttk.Button(
            button_frame,
            text="Clear All",
            command=self._on_clear
        ).pack(side=tk.RIGHT)

    def _build_settings_tab(self, parent):
        """Build the settings tab"""
        # API Settings
        api_frame = ttk.LabelFrame(parent, text="API Configuration", padding="10")
        api_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(api_frame, text="API Endpoint:").pack(anchor=tk.W)
        self.api_entry = ttk.Entry(api_frame, width=60)
        self.api_entry.insert(0, GOOGLE_TTS_API)
        self.api_entry.pack(fill=tk.X, pady=(5, 0))

        # Info section
        info_frame = ttk.LabelFrame(parent, text="Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = """
This application uses Google's Little Language Lessons (LLL) API to generate
high-quality text-to-speech audio using Chirp3-HD voices.

Features:
- Multiple languages and voice options
- Automatic text chunking for long texts
- Audio playback and MP3 export
- Progress tracking for long generations

Voice Model: Chirp3-HD
Audio Format: MP3

Note: This uses an experimental Google API and may have usage limitations.
        """

        info_label = ttk.Label(info_frame, text=info_text.strip(), justify=tk.LEFT)
        info_label.pack(anchor=tk.W)

        # Dependencies status
        deps_frame = ttk.LabelFrame(parent, text="Dependencies Status", padding="10")
        deps_frame.pack(fill=tk.X)

        pydub_status = "Installed" if PYDUB_AVAILABLE else "Not installed (audio merging may have artifacts)"
        pygame_status = "Installed" if PYGAME_AVAILABLE else "Not installed (using system player)"

        ttk.Label(deps_frame, text=f"pydub: {pydub_status}").pack(anchor=tk.W)
        ttk.Label(deps_frame, text=f"pygame: {pygame_status}").pack(anchor=tk.W)

    def _on_text_change(self, event=None):
        """Update character counter when text changes"""
        text = self.text_input.get("1.0", tk.END).strip()
        char_count = len(text)
        self.char_count_label.configure(text=f"Characters: {char_count}")

        # Calculate chunks
        try:
            chunk_size = int(self.chunk_size_var.get())
        except ValueError:
            chunk_size = 500

        if char_count > chunk_size:
            chunks = self.engine.split_text_into_chunks(text, chunk_size)
            self.chunk_info_label.configure(
                text=f"Will be split into {len(chunks)} chunks"
            )
        else:
            self.chunk_info_label.configure(text="")

    def _get_selected_language(self) -> str:
        """Extract language code from combo selection"""
        selection = self.language_var.get()
        return selection.split(" - ")[0]

    def _get_selected_voice(self) -> str:
        """Extract voice name from combo selection"""
        selection = self.voice_var.get()
        return selection.split(" (")[0]

    def _on_generate(self):
        """Start speech generation"""
        text = self.text_input.get("1.0", tk.END).strip()

        if not text:
            messagebox.showwarning("Warning", "Please enter some text to convert.")
            return

        if self.is_generating:
            return

        # Start generation in background thread
        self.is_generating = True
        self.generate_btn.configure(state=tk.DISABLED)
        self.play_btn.configure(state=tk.DISABLED)
        self.save_btn.configure(state=tk.DISABLED)
        self.progress_var.set(0)

        thread = threading.Thread(target=self._generate_speech_thread, args=(text,))
        thread.daemon = True
        thread.start()

    def _generate_speech_thread(self, text: str):
        """Background thread for speech generation"""
        try:
            language = self._get_selected_language()
            voice = self._get_selected_voice()

            try:
                chunk_size = int(self.chunk_size_var.get())
            except ValueError:
                chunk_size = 500

            # Split text into chunks
            chunks = self.engine.split_text_into_chunks(text, chunk_size)
            total_chunks = len(chunks)

            self._update_status(f"Generating speech... (0/{total_chunks} chunks)")

            audio_chunks = []

            for i, chunk in enumerate(chunks):
                self._update_status(f"Generating chunk {i+1}/{total_chunks}...")

                audio = self.engine.generate_speech(chunk, language, voice)

                if audio is None:
                    self._update_status(f"Error: Failed to generate chunk {i+1}")
                    self._generation_complete(False)
                    return

                audio_chunks.append(audio)
                progress = ((i + 1) / total_chunks) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

            # Concatenate all chunks
            if len(audio_chunks) > 1:
                self._update_status("Merging audio chunks...")
                self.current_audio = self.engine.concatenate_audio(audio_chunks)
            else:
                self.current_audio = audio_chunks[0]

            self._update_status("Generation complete!")
            self._generation_complete(True)

        except Exception as e:
            self._update_status(f"Error: {str(e)}")
            self._generation_complete(False)

    def _update_status(self, message: str):
        """Update status label from any thread"""
        self.root.after(0, lambda: self.status_label.configure(text=message))

    def _generation_complete(self, success: bool):
        """Called when generation is complete"""
        def update():
            self.is_generating = False
            self.generate_btn.configure(state=tk.NORMAL)
            if success:
                self.play_btn.configure(state=tk.NORMAL)
                self.save_btn.configure(state=tk.NORMAL)
                self.stop_btn.configure(state=tk.NORMAL)

        self.root.after(0, update)

    def _on_play(self):
        """Play the generated audio"""
        if self.current_audio is None:
            return

        # Save to temp file
        if self.temp_audio_file:
            try:
                os.remove(self.temp_audio_file)
            except:
                pass

        self.temp_audio_file = tempfile.mktemp(suffix='.mp3')
        with open(self.temp_audio_file, 'wb') as f:
            f.write(self.current_audio)

        if PYGAME_AVAILABLE:
            try:
                pygame.mixer.music.load(self.temp_audio_file)
                pygame.mixer.music.play()
                self._update_status("Playing audio...")
            except Exception as e:
                self._update_status(f"Playback error: {e}")
        else:
            # Use system default player
            import subprocess
            import platform

            system = platform.system()
            try:
                if system == 'Darwin':  # macOS
                    subprocess.Popen(['afplay', self.temp_audio_file])
                elif system == 'Windows':
                    os.startfile(self.temp_audio_file)
                else:  # Linux
                    subprocess.Popen(['xdg-open', self.temp_audio_file])
                self._update_status("Playing audio (external player)...")
            except Exception as e:
                self._update_status(f"Playback error: {e}")

    def _on_stop(self):
        """Stop audio playback"""
        if PYGAME_AVAILABLE:
            pygame.mixer.music.stop()
            self._update_status("Playback stopped")

    def _on_save(self):
        """Save audio to MP3 file"""
        if self.current_audio is None:
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")],
            initialname=f"speech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        )

        if filename:
            try:
                with open(filename, 'wb') as f:
                    f.write(self.current_audio)
                self._update_status(f"Saved to: {os.path.basename(filename)}")
                messagebox.showinfo("Success", f"Audio saved to:\n{filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}")

    def _on_clear(self):
        """Clear all inputs and generated audio"""
        self.text_input.delete("1.0", tk.END)
        self.current_audio = None
        self.progress_var.set(0)
        self.play_btn.configure(state=tk.DISABLED)
        self.save_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.DISABLED)
        self._update_status("Ready")
        self._on_text_change()

    def _on_close(self):
        """Cleanup on window close"""
        if PYGAME_AVAILABLE:
            pygame.mixer.quit()

        if self.temp_audio_file:
            try:
                os.remove(self.temp_audio_file)
            except:
                pass

        self.root.destroy()

    def run(self):
        """Start the application"""
        self.root.mainloop()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    app = TTSApplication()
    app.run()
