#!/usr/bin/env python3
"""
client_improved.py - Textual Chat Client with True Real-Time Streaming
=====================================================================

Versione migliorata del client con vero streaming real-time:
- Aggiornamento in-place della risposta AI
- Area dedicata per streaming live
- Typing indicators e progress visual
- Smooth streaming experience

Installazione richiesta:
    pip install textual httpx rich

Uso:
    python client_improved.py
"""

import asyncio
import sys
import json
from datetime import datetime
from typing import Optional

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, Switch
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel


class StreamingChatClient(App):
    """Client chat Textual con vero streaming real-time"""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #chat_log {
        height: 1fr;
        border: solid $accent;
        margin: 1;
        scrollbar-gutter: stable;
    }
    
    #streaming_area {
        height: 10;
        border: solid $success;
        margin: 1;
        scrollbar-gutter: stable;
        overflow-y: auto;
    }
    
    #main_container {
        height: 1fr;
    }
    
    #input_container {
        height: 4;
        dock: bottom;
    }
    
    #controls_container {
        height: 1;
        margin: 0 1;
    }
    
    #message_input {
        width: 1fr;
        margin: 0 1;
    }
    
    #send_button {
        width: 10;
        margin-right: 1;
    }
    
    #streaming_switch {
        width: 20;
        margin-right: 1;
    }
    
    #status_bar {
        height: 1;
        background: $surface;
        color: $text;
        text-align: center;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
        Binding("enter", "send_message", "Send", show=True),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+s", "toggle_streaming", "Toggle Streaming"),
    ]
    
    # Reactive variables for streaming state
    streaming_content = reactive("")
    streaming_active = reactive(False)
    typing_indicator = reactive(False)
    chunks_received = reactive(0)
    
    def __init__(self):
        super().__init__()
        self.api_base_url = "http://localhost:8000"
        self.session_id: Optional[str] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.streaming_enabled = True
        
        # Streaming state
        self.accumulated_content = ""
        self.streaming_task: Optional[asyncio.Task] = None
        
    def compose(self) -> ComposeResult:
        """Costruisce l'interfaccia utente"""
        yield Header()
        yield Container(
            RichLog(id="chat_log", highlight=True, markup=True),
            RichLog(id="streaming_area", highlight=True, markup=True),
            id="main_container"
        )
        yield Container(
            Horizontal(
                Switch(value=True, id="streaming_switch"),
                Static("Streaming Mode", id="streaming_label"),
                id="controls_container"
            ),
            Horizontal(
                Input(
                    placeholder="Scrivi il tuo messaggio qui...", 
                    id="message_input"
                ),
                Button("Send", variant="primary", id="send_button"),
            ),
            id="input_container"
        )
        yield Static("🔗 SimpleChatApp Real-Time Client | ESC/CTRL+C per uscire", id="status_bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Inizializzazione all'avvio"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Test connessione
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                self.log_message("🟢 Sistema", "Connesso al server SimpleChatApp")
                self.update_status("🟢 Connesso | Real-Time Streaming Ready")
            else:
                self.log_message("🔴 Sistema", f"Server errore: {response.status_code}")
        except Exception as e:
            self.log_message("🔴 Sistema", f"Connessione fallita: {e}")
        
        # Focus input
        self.query_one("#message_input").focus()
        
        # Setup streaming area watcher
        self.start_streaming_updater()
    
    def start_streaming_updater(self):
        """Avvia task per aggiornare streaming area"""
        async def update_streaming_display():
            while True:
                self.update_streaming_area()
                await asyncio.sleep(0.1)  # 10 FPS per smooth updates
        
        asyncio.create_task(update_streaming_display())
    
    def update_streaming_area(self):
        """Aggiorna l'area streaming in tempo reale"""
        streaming_log = self.query_one("#streaming_area", RichLog)
        
        if not self.streaming_active:
            # Area non attiva
            mode = "🔄 Streaming Mode" if self.streaming_enabled else "📡 Normal Mode"
            status_text = Text()
            status_text.append(f"{mode}\n", style="bold blue")
            status_text.append("Pronto per nuovi messaggi...", style="dim")
            streaming_log.clear()
            streaming_log.write(status_text)
            return
        
        # Streaming attivo - aggiorna contenuto
        streaming_log.clear()
        
        # Header con info
        header_text = Text()
        header_text.append("🤖 AI Real-Time Response", style="bold green")
        if self.chunks_received > 0:
            header_text.append(f" | 📦 {self.chunks_received} chunks", style="dim")
        header_text.append("\n" + "="*50 + "\n", style="dim")
        
        # Typing indicator
        if self.typing_indicator:
            header_text.append("💭 AI sta pensando", style="italic magenta")
            header_text.append(" ●●●", style="blink")
            header_text.append("\n\n")
        
        # Contenuto accumulato con word wrap
        if self.accumulated_content:
            # Word wrap manuale per contenuto lungo
            content_lines = []
            words = self.accumulated_content.split(' ')
            current_line = ""
            max_width = 80  # Larghezza massima per riga
            
            for word in words:
                # Se aggiungere la parola supera la larghezza, inizia nuova riga
                if len(current_line + " " + word) > max_width and current_line:
                    content_lines.append(current_line)
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            
            # Aggiungi l'ultima riga
            if current_line:
                content_lines.append(current_line)
            
            # Crea il testo con word wrap
            content_text = Text()
            for i, line in enumerate(content_lines):
                content_text.append(line)
                if i < len(content_lines) - 1:  # Non aggiungere \n all'ultima riga
                    content_text.append("\n")
            
            # Cursore lampeggiante solo sull'ultima riga se streaming attivo
            if self.streaming_active:
                content_text.append(" ▋", style="blink bold yellow")
            
            streaming_log.write(header_text)
            streaming_log.write(content_text)
        else:
            streaming_log.write(header_text)
    
    def log_message(self, sender: str, message: str, is_error: bool = False):
        """Aggiunge messaggio al log principale"""
        chat_log = self.query_one("#chat_log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if is_error:
            color = "red"
        elif sender == "🟢 Sistema":
            color = "green"
        elif sender == "Tu":
            color = "blue"
        else:
            color = "cyan"
        
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style=f"bold {color}")
        text.append(message)
        
        chat_log.write(text)
    
    def update_status(self, status: str):
        """Aggiorna barra di stato"""
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(status)
    
    async def create_session(self):
        """Crea una nuova sessione all'avvio"""
        try:
            response = await self.http_client.post(f"{self.api_base_url}/session/new")
            if response.status_code == 200:
                data = response.json()
                self.session_id = data["session_id"]
                self.log_message("🆕 Sessione", f"Creata: {self.session_id}")
            else:
                self.log_message("🟡 Sessione", "Creazione fallita, userò auto-generated")
        except Exception as e:
            self.log_message("🟡 Sessione", f"Errore creazione: {e}")
    
    async def send_message_streaming(self, message: str):
        """Streaming con aggiornamento real-time"""
        self.streaming_active = True
        self.typing_indicator = True
        self.accumulated_content = ""
        self.chunks_received = 0
        
        try:
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            async with self.http_client.stream(
                "POST",
                f"{self.api_base_url}/chat",
                json=payload
            ) as response:
                
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}"
                    self.log_message("🔴 Errore", error_msg, is_error=True)
                    return
                
                self.typing_indicator = False
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])
                            event_type = event_data.get("type")
                            
                            if event_type == "connection":
                                thread_id = event_data.get("thread_id")
                                if not self.session_id:
                                    self.session_id = thread_id
                                self.log_message("🔄 Sistema", f"Thread: {thread_id}")
                                
                            elif event_type == "start":
                                self.log_message("🔄 Sistema", "Elaborazione iniziata...")
                                
                            elif event_type == "content":
                                chunk = event_data.get("chunk", "")
                                self.accumulated_content += chunk
                                self.chunks_received += 1
                                
                                # L'aggiornamento visual è gestito dal loop automatico
                                
                            elif event_type == "complete":
                                final_content = event_data.get("final_content", self.accumulated_content)
                                total_chunks = event_data.get("total_chunks", self.chunks_received)
                                
                                # Aggiungi al log principale
                                self.log_message("🤖 AI", f"{final_content} [{total_chunks} chunks]")
                                
                                self.streaming_active = False
                                break
                                
                            elif event_type == "error":
                                error_msg = event_data.get("error", "Errore sconosciuto")
                                self.log_message("🔴 Errore", f"Streaming: {error_msg}", is_error=True)
                                self.streaming_active = False
                                break
                                
                            elif event_type == "done":
                                self.streaming_active = False
                                break
                                
                        except json.JSONDecodeError:
                            continue
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Streaming: {e}", is_error=True)
        finally:
            self.streaming_active = False
            self.typing_indicator = False
    
    async def send_message_normal(self, message: str):
        """Invio normale"""
        try:
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/query",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if not self.session_id:
                    self.session_id = data.get("session_id")
                
                result = data.get("result", "Nessuna risposta")
                doc_count = data.get("document_count", 0)
                
                ai_message = f"{result}"
                if doc_count > 0:
                    ai_message += f" ({doc_count} documenti)"
                
                self.log_message("🤖 AI", ai_message)
                
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
                error_msg = error_data.get("message", error_data.get("detail", "Errore sconosciuto"))
                self.log_message("🔴 Errore", f"HTTP {response.status_code}: {error_msg}", is_error=True)
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Connessione: {e}", is_error=True)
    
    async def send_message(self, message: str):
        """Invia messaggio"""
        if not message.strip():
            return
        
        self.log_message("Tu", message)
        
        if self.streaming_enabled:
            await self.send_message_streaming(message)
        else:
            await self.send_message_normal(message)
    
    async def action_send_message(self) -> None:
        """Azione invio messaggio"""
        message_input = self.query_one("#message_input", Input)
        message = message_input.value

        if message.strip():
            message_input.value = ""
            try:
                await self.send_message(message)
            except Exception as e:
                self.log_message("🔴 Sistema", f"Errore invio: {e}", is_error=True)
    
    async def on_switch_changed(self, event) -> None:
        """Toggle streaming mode"""
        if event.switch.id == "streaming_switch":
            self.streaming_enabled = event.value
            mode = "Streaming" if self.streaming_enabled else "Normal"
            self.log_message("🟢 Sistema", f"Modalità: {mode}")
            
            status_mode = "Real-Time Streaming" if self.streaming_enabled else "Normal Mode"
            self.update_status(f"🟢 Connesso | {status_mode}")
    
    def action_toggle_streaming(self) -> None:
        """Toggle streaming via CTRL+S"""
        switch = self.query_one("#streaming_switch", Switch)
        switch.value = not switch.value
        self.streaming_enabled = switch.value
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Click bottoni"""
        if event.button.id == "send_button":
            await self.action_send_message()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter su input"""
        if event.input.id == "message_input":
            await self.action_send_message()
    
    def action_clear_chat(self) -> None:
        """Pulisce chat (CTRL+L)"""
        chat_log = self.query_one("#chat_log", RichLog)
        streaming_log = self.query_one("#streaming_area", RichLog)
        chat_log.clear()
        streaming_log.clear()
        self.log_message("🟢 Sistema", "Chat pulita")
        self.session_id = None
        self.accumulated_content = ""
        self.streaming_active = False

    async def on_unmount(self) -> None:
        """Pulizia alla chiusura"""
        if self.http_client:
            await self.http_client.aclose()

    def action_quit(self) -> None:
        """Termina applicazione"""
        self.exit()


def main():
    """Funzione principale"""
    try:
        app = StreamingChatClient()
        app.title = "SimpleChatApp Real-Time Client v3.0"
        app.sub_title = "Real-Time Streaming Chat with Live Updates"
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
