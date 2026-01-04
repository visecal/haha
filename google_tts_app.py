#!/usr/bin/env python3
"""
Google TTS Desktop Application
Using Google's Little Language Lessons (LLL) API
Supports text chunking for long texts, SRT subtitle processing, and multiple voices/languages
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import base64
import threading
import os
import tempfile
import io
import time
from datetime import datetime
from typing import Optional, List, Tuple, NamedTuple
from dataclasses import dataclass
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

# API Limits (based on research)
API_LIMITS = {
    "max_bytes_per_request": 5000,  # ~600-1000 characters
    "recommended_chunk_size": 500,   # Safe limit for most languages
    "rate_limit_delay": 0.5,         # Delay between requests (seconds)
}

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
# SRT PARSER
# =============================================================================

@dataclass
class SubtitleEntry:
    """Represents a single subtitle entry"""
    index: int
    start_time: float  # in seconds
    end_time: float    # in seconds
    text: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class SRTParser:
    """Parse SRT subtitle files"""

    @staticmethod
    def parse_timestamp(timestamp: str) -> float:
        """
        Parse SRT timestamp to seconds

        Format: HH:MM:SS,mmm or HH:MM:SS.mmm
        """
        # Handle both comma and dot as decimal separator
        timestamp = timestamp.replace(',', '.')

        parts = timestamp.split(':')
        if len(parts) != 3:
            raise ValueError(f"Invalid timestamp format: {timestamp}")

        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])

        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        """Format seconds to SRT timestamp"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60

        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

    @classmethod
    def parse_file(cls, filepath: str, encoding: str = 'utf-8') -> List[SubtitleEntry]:
        """Parse an SRT file and return list of subtitle entries"""
        encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

        content = None
        for enc in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            raise ValueError(f"Could not decode file with any supported encoding")

        return cls.parse_content(content)

    @classmethod
    def parse_content(cls, content: str) -> List[SubtitleEntry]:
        """Parse SRT content string and return list of subtitle entries"""
        entries = []

        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Split into blocks (separated by blank lines)
        blocks = re.split(r'\n\s*\n', content.strip())

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            lines = block.split('\n')
            if len(lines) < 3:
                continue

            try:
                # First line: index
                index = int(lines[0].strip())

                # Second line: timestamps
                time_line = lines[1].strip()
                time_match = re.match(
                    r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})',
                    time_line
                )

                if not time_match:
                    continue

                start_time = cls.parse_timestamp(time_match.group(1))
                end_time = cls.parse_timestamp(time_match.group(2))

                # Remaining lines: text
                text = '\n'.join(lines[2:]).strip()

                # Remove HTML tags if present
                text = re.sub(r'<[^>]+>', '', text)

                if text:
                    entries.append(SubtitleEntry(
                        index=index,
                        start_time=start_time,
                        end_time=end_time,
                        text=text
                    ))

            except (ValueError, IndexError) as e:
                print(f"Warning: Skipping malformed subtitle block: {e}")
                continue

        return entries


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
        self.cancel_requested = False

    def cancel(self):
        """Request cancellation of ongoing operation"""
        self.cancel_requested = True

    def reset_cancel(self):
        """Reset cancellation flag"""
        self.cancel_requested = False

    def generate_speech(self, text: str, language_code: str, voice_name: str,
                        retry_count: int = 3, retry_delay: float = 1.0) -> Optional[bytes]:
        """
        Generate speech from text using Google LLL API

        Args:
            text: Text to convert to speech
            language_code: Language code (e.g., 'en-US')
            voice_name: Voice name (e.g., 'Orus')
            retry_count: Number of retries on failure
            retry_delay: Delay between retries

        Returns:
            MP3 audio bytes or None if failed
        """
        full_voice_name = f"{language_code}-Chirp3-HD-{voice_name}"

        payload = {
            "text": text,
            "languageCode": language_code,
            "voiceName": full_voice_name
        }

        for attempt in range(retry_count):
            if self.cancel_requested:
                return None

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
                print(f"API request failed (attempt {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(retry_delay * (attempt + 1))
                continue
            except Exception as e:
                print(f"Error generating speech: {e}")
                return None

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

    def concatenate_audio_with_timing(
        self,
        audio_data: List[Tuple[bytes, float, float]],
        gap_padding: float = 0.0
    ) -> bytes:
        """
        Concatenate audio chunks with timing information

        Args:
            audio_data: List of (audio_bytes, start_time, end_time) tuples
            gap_padding: Extra silence padding between clips (seconds)

        Returns:
            Combined MP3 audio bytes
        """
        if not PYDUB_AVAILABLE:
            # Without pydub, just concatenate without timing
            return self.concatenate_audio([a[0] for a in audio_data])

        combined = AudioSegment.empty()
        current_position = 0.0  # in seconds

        for audio_bytes, start_time, end_time in audio_data:
            # Add silence if there's a gap
            gap = start_time - current_position
            if gap > 0:
                silence_duration = int((gap + gap_padding) * 1000)  # Convert to ms
                if silence_duration > 0:
                    silence = AudioSegment.silent(duration=silence_duration)
                    combined += silence

            # Add the audio
            segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
            combined += segment

            current_position = start_time + len(segment) / 1000.0

        output = io.BytesIO()
        combined.export(output, format="mp3")
        return output.getvalue()

    def create_silence(self, duration_ms: int) -> bytes:
        """Create silent audio of specified duration"""
        if PYDUB_AVAILABLE:
            silence = AudioSegment.silent(duration=duration_ms)
            output = io.BytesIO()
            silence.export(output, format="mp3")
            return output.getvalue()
        else:
            # Return empty bytes if pydub not available
            return b''


# =============================================================================
# GUI APPLICATION
# =============================================================================

class TTSApplication:
    """Main TTS Desktop Application"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Google TTS Desktop - Chirp3-HD Voices")
        self.root.geometry("950x800")
        self.root.minsize(850, 700)

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
        self.style.configure('Success.TLabel', foreground='green')
        self.style.configure('Error.TLabel', foreground='red')

        # Initialize engine
        self.engine = TTSEngine()

        # State variables
        self.current_audio: Optional[bytes] = None
        self.is_generating = False
        self.temp_audio_file: Optional[str] = None

        # SRT state
        self.srt_entries: List[SubtitleEntry] = []
        self.srt_audio_files: List[Tuple[int, bytes]] = []  # (index, audio_bytes)

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
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Main TTS Tab
        tts_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tts_frame, text="Text to Speech")

        # SRT Tab
        srt_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(srt_frame, text="SRT to Voice")

        # Settings Tab
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="Settings")

        self._build_tts_tab(tts_frame)
        self._build_srt_tab(srt_frame)
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

    def _build_srt_tab(self, parent):
        """Build the SRT to Voice interface"""
        # File selection section
        file_frame = ttk.LabelFrame(parent, text="SRT File", padding="10")
        file_frame.pack(fill=tk.X, pady=(0, 10))

        file_row = ttk.Frame(file_frame)
        file_row.pack(fill=tk.X)

        self.srt_path_var = tk.StringVar()
        srt_entry = ttk.Entry(file_row, textvariable=self.srt_path_var, state='readonly')
        srt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Button(
            file_row,
            text="Browse...",
            command=self._on_browse_srt
        ).pack(side=tk.LEFT)

        # SRT Preview section
        preview_frame = ttk.LabelFrame(parent, text="Subtitle Preview", padding="10")
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview for subtitles
        columns = ('index', 'time', 'text')
        self.srt_tree = ttk.Treeview(preview_frame, columns=columns, show='headings', height=8)

        self.srt_tree.heading('index', text='#')
        self.srt_tree.heading('time', text='Time')
        self.srt_tree.heading('text', text='Text')

        self.srt_tree.column('index', width=50, minwidth=50)
        self.srt_tree.column('time', width=150, minwidth=150)
        self.srt_tree.column('text', width=500, minwidth=200)

        srt_scroll = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.srt_tree.yview)
        self.srt_tree.configure(yscrollcommand=srt_scroll.set)

        self.srt_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        srt_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # SRT Info
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        self.srt_info_label = ttk.Label(info_frame, text="No file loaded", foreground='#666')
        self.srt_info_label.pack(side=tk.LEFT)

        # Voice settings for SRT
        srt_settings_frame = ttk.LabelFrame(parent, text="Voice Settings", padding="10")
        srt_settings_frame.pack(fill=tk.X, pady=(0, 10))

        srt_settings_grid = ttk.Frame(srt_settings_frame)
        srt_settings_grid.pack(fill=tk.X)

        # Language selection for SRT
        ttk.Label(srt_settings_grid, text="Language:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.srt_language_var = tk.StringVar(value="en-US")
        self.srt_language_combo = ttk.Combobox(
            srt_settings_grid,
            textvariable=self.srt_language_var,
            values=[f"{code} - {name}" for code, name in LANGUAGES],
            state='readonly',
            width=30
        )
        self.srt_language_combo.current(0)
        self.srt_language_combo.grid(row=0, column=1, sticky=tk.W, pady=5)

        # Voice selection for SRT
        ttk.Label(srt_settings_grid, text="Voice:").grid(row=0, column=2, sticky=tk.W, padx=(20, 10))
        self.srt_voice_var = tk.StringVar(value="Orus")
        self.srt_voice_combo = ttk.Combobox(
            srt_settings_grid,
            textvariable=self.srt_voice_var,
            values=[f"{v[0]} ({v[2]}) - {v[3]}" for v in VOICES],
            state='readonly',
            width=30
        )
        self.srt_voice_combo.current(6)
        self.srt_voice_combo.grid(row=0, column=3, sticky=tk.W, pady=5)

        # Options row
        options_frame = ttk.Frame(srt_settings_frame)
        options_frame.pack(fill=tk.X, pady=(10, 0))

        # Use timing checkbox
        self.use_timing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options_frame,
            text="Use SRT timing (add silence gaps)",
            variable=self.use_timing_var
        ).pack(side=tk.LEFT, padx=(0, 20))

        # Gap padding
        ttk.Label(options_frame, text="Extra gap:").pack(side=tk.LEFT, padx=(0, 5))
        self.gap_padding_var = tk.StringVar(value="0.2")
        gap_spinbox = ttk.Spinbox(
            options_frame,
            from_=0,
            to=5,
            increment=0.1,
            textvariable=self.gap_padding_var,
            width=6
        )
        gap_spinbox.pack(side=tk.LEFT)
        ttk.Label(options_frame, text="sec", foreground='#666').pack(side=tk.LEFT, padx=(5, 20))

        # Rate limit delay
        ttk.Label(options_frame, text="API delay:").pack(side=tk.LEFT, padx=(0, 5))
        self.rate_delay_var = tk.StringVar(value="0.5")
        rate_spinbox = ttk.Spinbox(
            options_frame,
            from_=0,
            to=5,
            increment=0.1,
            textvariable=self.rate_delay_var,
            width=6
        )
        rate_spinbox.pack(side=tk.LEFT)
        ttk.Label(options_frame, text="sec", foreground='#666').pack(side=tk.LEFT)

        # Progress section for SRT
        srt_progress_frame = ttk.Frame(parent)
        srt_progress_frame.pack(fill=tk.X, pady=(0, 10))

        self.srt_progress_var = tk.DoubleVar(value=0)
        self.srt_progress_bar = ttk.Progressbar(
            srt_progress_frame,
            variable=self.srt_progress_var,
            maximum=100
        )
        self.srt_progress_bar.pack(fill=tk.X, pady=(0, 5))

        self.srt_status_label = ttk.Label(srt_progress_frame, text="Ready", foreground='#666')
        self.srt_status_label.pack(side=tk.LEFT)

        # Action buttons for SRT
        srt_button_frame = ttk.Frame(parent)
        srt_button_frame.pack(fill=tk.X)

        self.srt_generate_btn = ttk.Button(
            srt_button_frame,
            text="Generate All",
            command=self._on_generate_srt
        )
        self.srt_generate_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.srt_cancel_btn = ttk.Button(
            srt_button_frame,
            text="Cancel",
            command=self._on_cancel_srt,
            state=tk.DISABLED
        )
        self.srt_cancel_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.srt_play_btn = ttk.Button(
            srt_button_frame,
            text="Play",
            command=self._on_play_srt,
            state=tk.DISABLED
        )
        self.srt_play_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.srt_save_btn = ttk.Button(
            srt_button_frame,
            text="Save MP3",
            command=self._on_save_srt,
            state=tk.DISABLED
        )
        self.srt_save_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.srt_save_individual_btn = ttk.Button(
            srt_button_frame,
            text="Save Individual Files",
            command=self._on_save_individual_srt,
            state=tk.DISABLED
        )
        self.srt_save_individual_btn.pack(side=tk.LEFT)

        # Clear button on right
        ttk.Button(
            srt_button_frame,
            text="Clear",
            command=self._on_clear_srt
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

        # API Limits info
        limits_frame = ttk.LabelFrame(parent, text="API Limits (Research)", padding="10")
        limits_frame.pack(fill=tk.X, pady=(0, 10))

        limits_text = """
Known Limits for Google LLL API:
• Max ~5000 bytes per request (~600-1000 characters depending on language)
• No official rate limit documented (experimental API)
• Recommended: Add 0.3-0.5s delay between requests to avoid throttling

Google Cloud TTS (official - for comparison):
• Chirp3-HD: 200 requests/minute
• Free tier: 1 million characters/month
        """
        ttk.Label(limits_frame, text=limits_text.strip(), justify=tk.LEFT).pack(anchor=tk.W)

        # Info section
        info_frame = ttk.LabelFrame(parent, text="Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = """
Features:
• Text to Speech with automatic chunking
• SRT subtitle file to voice conversion
• Multiple languages and 20+ voice options
• Audio playback and MP3 export
• Timing-aware audio generation for SRT

Voice Model: Chirp3-HD
Audio Format: MP3
        """
        ttk.Label(info_frame, text=info_text.strip(), justify=tk.LEFT).pack(anchor=tk.W)

        # Dependencies status
        deps_frame = ttk.LabelFrame(parent, text="Dependencies Status", padding="10")
        deps_frame.pack(fill=tk.X)

        pydub_status = "✓ Installed" if PYDUB_AVAILABLE else "✗ Not installed (timing features disabled)"
        pygame_status = "✓ Installed" if PYGAME_AVAILABLE else "✗ Not installed (using system player)"

        pydub_style = 'Success.TLabel' if PYDUB_AVAILABLE else 'Error.TLabel'
        pygame_style = 'Success.TLabel' if PYGAME_AVAILABLE else 'Error.TLabel'

        ttk.Label(deps_frame, text=f"pydub: {pydub_status}", style=pydub_style).pack(anchor=tk.W)
        ttk.Label(deps_frame, text=f"pygame: {pygame_status}", style=pygame_style).pack(anchor=tk.W)

        if not PYDUB_AVAILABLE:
            ttk.Label(
                deps_frame,
                text="  Install: pip install pydub (requires ffmpeg)",
                foreground='#666'
            ).pack(anchor=tk.W)

    # =========================================================================
    # TTS Tab Methods
    # =========================================================================

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
        self.engine.reset_cancel()
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
                if self.engine.cancel_requested:
                    self._update_status("Cancelled")
                    self._generation_complete(False)
                    return

                self._update_status(f"Generating chunk {i+1}/{total_chunks}...")

                audio = self.engine.generate_speech(chunk, language, voice)

                if audio is None:
                    self._update_status(f"Error: Failed to generate chunk {i+1}")
                    self._generation_complete(False)
                    return

                audio_chunks.append(audio)
                progress = ((i + 1) / total_chunks) * 100
                self.root.after(0, lambda p=progress: self.progress_var.set(p))

                # Add small delay between requests
                if i < total_chunks - 1:
                    time.sleep(0.3)

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

        self._play_audio(self.current_audio)

    def _play_audio(self, audio_bytes: bytes):
        """Play audio bytes"""
        # Save to temp file
        if self.temp_audio_file:
            try:
                os.remove(self.temp_audio_file)
            except:
                pass

        self.temp_audio_file = tempfile.mktemp(suffix='.mp3')
        with open(self.temp_audio_file, 'wb') as f:
            f.write(audio_bytes)

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

        self._save_audio(self.current_audio, "speech")

    def _save_audio(self, audio_bytes: bytes, prefix: str = "audio"):
        """Save audio bytes to file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".mp3",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")],
            initialfilename=f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        )

        if filename:
            try:
                with open(filename, 'wb') as f:
                    f.write(audio_bytes)
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

    # =========================================================================
    # SRT Tab Methods
    # =========================================================================

    def _on_browse_srt(self):
        """Browse for SRT file"""
        filename = filedialog.askopenfilename(
            filetypes=[
                ("SRT files", "*.srt"),
                ("All files", "*.*")
            ]
        )

        if filename:
            self._load_srt_file(filename)

    def _load_srt_file(self, filepath: str):
        """Load and parse SRT file"""
        try:
            self.srt_entries = SRTParser.parse_file(filepath)

            if not self.srt_entries:
                messagebox.showwarning("Warning", "No valid subtitles found in file.")
                return

            self.srt_path_var.set(filepath)

            # Clear existing items
            for item in self.srt_tree.get_children():
                self.srt_tree.delete(item)

            # Add entries to tree
            total_chars = 0
            for entry in self.srt_entries:
                time_str = f"{SRTParser.format_timestamp(entry.start_time)} --> {SRTParser.format_timestamp(entry.end_time)}"
                # Truncate long text for display
                display_text = entry.text.replace('\n', ' ')
                if len(display_text) > 80:
                    display_text = display_text[:77] + "..."

                self.srt_tree.insert('', tk.END, values=(entry.index, time_str, display_text))
                total_chars += len(entry.text)

            # Update info
            duration = self.srt_entries[-1].end_time if self.srt_entries else 0
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"

            self.srt_info_label.configure(
                text=f"Loaded: {len(self.srt_entries)} subtitles | Duration: {duration_str} | Total chars: {total_chars}"
            )

            # Enable generate button
            self.srt_generate_btn.configure(state=tk.NORMAL)
            self.srt_audio_files = []
            self.srt_play_btn.configure(state=tk.DISABLED)
            self.srt_save_btn.configure(state=tk.DISABLED)
            self.srt_save_individual_btn.configure(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load SRT file:\n{e}")

    def _get_srt_language(self) -> str:
        """Extract language code from SRT combo selection"""
        selection = self.srt_language_var.get()
        return selection.split(" - ")[0]

    def _get_srt_voice(self) -> str:
        """Extract voice name from SRT combo selection"""
        selection = self.srt_voice_var.get()
        return selection.split(" (")[0]

    def _on_generate_srt(self):
        """Generate voice for all SRT entries"""
        if not self.srt_entries:
            messagebox.showwarning("Warning", "Please load an SRT file first.")
            return

        if self.is_generating:
            return

        self.is_generating = True
        self.engine.reset_cancel()
        self.srt_generate_btn.configure(state=tk.DISABLED)
        self.srt_cancel_btn.configure(state=tk.NORMAL)
        self.srt_play_btn.configure(state=tk.DISABLED)
        self.srt_save_btn.configure(state=tk.DISABLED)
        self.srt_save_individual_btn.configure(state=tk.DISABLED)
        self.srt_progress_var.set(0)

        thread = threading.Thread(target=self._generate_srt_thread)
        thread.daemon = True
        thread.start()

    def _generate_srt_thread(self):
        """Background thread for SRT voice generation"""
        try:
            language = self._get_srt_language()
            voice = self._get_srt_voice()

            try:
                rate_delay = float(self.rate_delay_var.get())
            except ValueError:
                rate_delay = 0.5

            total = len(self.srt_entries)
            self.srt_audio_files = []

            for i, entry in enumerate(self.srt_entries):
                if self.engine.cancel_requested:
                    self._update_srt_status("Cancelled")
                    self._srt_generation_complete(False)
                    return

                self._update_srt_status(f"Generating {i+1}/{total}: \"{entry.text[:30]}...\"")

                # Generate audio for this entry
                audio = self.engine.generate_speech(entry.text, language, voice)

                if audio is None:
                    self._update_srt_status(f"Error on entry {i+1}, retrying...")
                    time.sleep(1)
                    audio = self.engine.generate_speech(entry.text, language, voice)

                    if audio is None:
                        self._update_srt_status(f"Failed to generate entry {i+1}")
                        self._srt_generation_complete(False)
                        return

                self.srt_audio_files.append((entry.index, audio, entry.start_time, entry.end_time))

                progress = ((i + 1) / total) * 100
                self.root.after(0, lambda p=progress: self.srt_progress_var.set(p))

                # Rate limiting
                if i < total - 1:
                    time.sleep(rate_delay)

            self._update_srt_status(f"Generated {total} audio clips successfully!")
            self._srt_generation_complete(True)

        except Exception as e:
            self._update_srt_status(f"Error: {str(e)}")
            self._srt_generation_complete(False)

    def _update_srt_status(self, message: str):
        """Update SRT status label from any thread"""
        self.root.after(0, lambda: self.srt_status_label.configure(text=message))

    def _srt_generation_complete(self, success: bool):
        """Called when SRT generation is complete"""
        def update():
            self.is_generating = False
            self.srt_generate_btn.configure(state=tk.NORMAL)
            self.srt_cancel_btn.configure(state=tk.DISABLED)
            if success and self.srt_audio_files:
                self.srt_play_btn.configure(state=tk.NORMAL)
                self.srt_save_btn.configure(state=tk.NORMAL)
                self.srt_save_individual_btn.configure(state=tk.NORMAL)

        self.root.after(0, update)

    def _on_cancel_srt(self):
        """Cancel ongoing SRT generation"""
        self.engine.cancel()
        self._update_srt_status("Cancelling...")

    def _on_play_srt(self):
        """Play combined SRT audio"""
        if not self.srt_audio_files:
            return

        # Combine audio with or without timing
        use_timing = self.use_timing_var.get() and PYDUB_AVAILABLE

        if use_timing:
            try:
                gap_padding = float(self.gap_padding_var.get())
            except ValueError:
                gap_padding = 0.2

            audio_data = [(audio, start, end) for idx, audio, start, end in self.srt_audio_files]
            combined = self.engine.concatenate_audio_with_timing(audio_data, gap_padding)
        else:
            combined = self.engine.concatenate_audio([audio for idx, audio, start, end in self.srt_audio_files])

        self._play_audio(combined)

    def _on_save_srt(self):
        """Save combined SRT audio"""
        if not self.srt_audio_files:
            return

        use_timing = self.use_timing_var.get() and PYDUB_AVAILABLE

        if use_timing:
            try:
                gap_padding = float(self.gap_padding_var.get())
            except ValueError:
                gap_padding = 0.2

            audio_data = [(audio, start, end) for idx, audio, start, end in self.srt_audio_files]
            combined = self.engine.concatenate_audio_with_timing(audio_data, gap_padding)
        else:
            combined = self.engine.concatenate_audio([audio for idx, audio, start, end in self.srt_audio_files])

        # Get original filename for prefix
        srt_path = self.srt_path_var.get()
        prefix = os.path.splitext(os.path.basename(srt_path))[0] if srt_path else "srt_voice"

        self._save_audio(combined, prefix)

    def _on_save_individual_srt(self):
        """Save individual audio files for each subtitle"""
        if not self.srt_audio_files:
            return

        # Ask for output directory
        output_dir = filedialog.askdirectory(title="Select Output Directory")

        if not output_dir:
            return

        try:
            srt_path = self.srt_path_var.get()
            base_name = os.path.splitext(os.path.basename(srt_path))[0] if srt_path else "subtitle"

            saved_count = 0
            for idx, audio, start, end in self.srt_audio_files:
                filename = f"{base_name}_{idx:04d}.mp3"
                filepath = os.path.join(output_dir, filename)

                with open(filepath, 'wb') as f:
                    f.write(audio)
                saved_count += 1

            messagebox.showinfo(
                "Success",
                f"Saved {saved_count} audio files to:\n{output_dir}"
            )
            self._update_srt_status(f"Saved {saved_count} files")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save files:\n{e}")

    def _on_clear_srt(self):
        """Clear SRT data"""
        self.srt_entries = []
        self.srt_audio_files = []
        self.srt_path_var.set("")

        for item in self.srt_tree.get_children():
            self.srt_tree.delete(item)

        self.srt_info_label.configure(text="No file loaded")
        self.srt_progress_var.set(0)
        self.srt_generate_btn.configure(state=tk.DISABLED)
        self.srt_play_btn.configure(state=tk.DISABLED)
        self.srt_save_btn.configure(state=tk.DISABLED)
        self.srt_save_individual_btn.configure(state=tk.DISABLED)
        self._update_srt_status("Ready")

    # =========================================================================
    # Application Methods
    # =========================================================================

    def _on_close(self):
        """Cleanup on window close"""
        self.engine.cancel()

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
