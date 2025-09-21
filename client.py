#!/usr/bin/env python3
"""
client.py - Textual Chat Client for SimpleChatApp with Streaming Support
=======================================================================

Un client chat avanzato che utilizza Textual per interagire con l'API REST.
Supporta sia endpoint normale (/query) che streaming (/chat).
Terminazione tramite CTRL+C o ESC.

Installazione richiesta:
    pip install textual httpx

Uso:
    python client.py
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
from rich.text import Text
from rich.panel import Panel


class ChatClient(App):
    """Client chat Textual per SimpleChatApp API con supporto streaming"""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #chat_log {
        height: 1fr;
        border: solid $accent;
        margin: 1;
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
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
        Binding("enter", "send_message", "Send", show=True),
        ("ctrl+l", "clear_chat", "Clear Chat"),
        ("ctrl+s", "toggle_streaming", "Toggle Streaming"),
    ]
    
    def __init__(self):
        super().__init__()
        self.api_base_url = "http://localhost:8000"
        self.session_id: Optional[str] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.streaming_enabled = True  # Default streaming abilitato
        self.streaming_message_placeholder = None  # Track streaming placeholder
        self.last_chunk_display_time = 0  # Throttling per chunk display
        
    def compose(self) -> ComposeResult:
        """Costruisce l'interfaccia utente"""
        yield Header()
        yield Container(
            RichLog(id="chat_log", highlight=True, markup=True),
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
        yield Static("🔗 Connesso a http://localhost:8000 | ESC/CTRL+C per uscire | CTRL+S per toggle streaming", id="status_bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Inizializzazione all'avvio"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Test connessione API
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                self.log_message("🟢 Sistema", "Connesso al server SimpleChatApp")
                self.update_status("🟢 Connesso | Streaming Mode ON | Pronto per chattare")
            else:
                self.log_message("🔴 Sistema", f"Server risponde ma con errore: {response.status_code}")
                self.update_status("🟡 Connessione instabile")
        except Exception as e:
            self.log_message("🔴 Sistema", f"Impossibile connettersi al server: {e}")
            self.update_status("🔴 Server non raggiungibile")
        
        # Focus sull'input
        self.query_one("#message_input").focus()
    
    async def on_unmount(self) -> None:
        """Pulizia alla chiusura"""
        if self.http_client:
            await self.http_client.aclose()
    
    def log_message(self, sender: str, message: str, is_error: bool = False, is_streaming: bool = False):
        """Aggiunge un messaggio al log della chat"""
        chat_log = self.query_one("#chat_log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if is_error:
            color = "red"
        elif sender == "🟢 Sistema":
            color = "green"
        elif sender == "Tu":
            color = "blue"
        elif is_streaming:
            color = "magenta"
        else:
            color = "cyan"
        
        # Crea il messaggio formattato
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style=f"bold {color}")
        text.append(message)
        
        chat_log.write(text)
    
    def start_streaming_message(self, sender: str):
        """Inizia un nuovo messaggio streaming"""
        chat_log = self.query_one("#chat_log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Salva la posizione per successivi update
        self.streaming_message_placeholder = f"streaming_{timestamp}"
        
        # Aggiungi messaggio placeholder per streaming
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style="bold magenta")
        text.append("⏳ Streaming in corso...")
        
        chat_log.write(text)
    
    def update_streaming_message(self, sender: str, partial_message: str):
        """Mostra chunk streaming con throttling"""
        import time
        
        # Throttling: mostra max ogni 0.2 secondi per evitare spam
        current_time = time.time()
        if current_time - self.last_chunk_display_time < 0.2:
            return  # Skip questo chunk
        
        self.last_chunk_display_time = current_time
        
        chat_log = self.query_one("#chat_log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Mostra chunk con indicatore streaming
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style="bold yellow")  # Colore diverso per chunk
        text.append(partial_message + " ▋")  # Cursore per indicare streaming attivo
        
        chat_log.write(text)
    
    def finalize_streaming_message(self, sender: str, final_message: str, extra_info: str = ""):
        """Finalizza il messaggio streaming"""
        chat_log = self.query_one("#chat_log", RichLog)
        
        # Semplicemente aggiungi il messaggio finale
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style="bold cyan")  # Cambio colore per distinguere
        text.append(final_message)
        if extra_info:
            text.append(f" {extra_info}", style="dim")
        
        chat_log.write(text)
        self.streaming_message_placeholder = None  # Reset
    
    def update_status(self, status: str):
        """Aggiorna la barra di stato"""
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(status)
    
    async def send_message_normal(self, message: str):
        """Invia messaggio via endpoint normale /query"""
        self.update_status("📡 Invio messaggio (normale)...")
        
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
                
                # Salva session_id per messaggi futuri
                if not self.session_id:
                    self.session_id = data.get("session_id")
                
                # Mostra la risposta
                result = data.get("result", "Nessuna risposta")
                doc_count = data.get("document_count", 0)
                
                ai_message = f"{result}"
                if doc_count > 0:
                    ai_message += f" ({doc_count} documenti)"
                
                self.log_message("🤖 AI (Normal)", ai_message)
                self.update_status("✅ Messaggio inviato (normale)")
                
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
                error_msg = error_data.get("message", error_data.get("detail", "Errore sconosciuto"))
                self.log_message("🔴 Errore", f"HTTP {response.status_code}: {error_msg}", is_error=True)
                self.update_status("❌ Errore nella richiesta")
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore di connessione: {e}", is_error=True)
            self.update_status("❌ Errore di connessione")
    
    async def send_message_streaming(self, message: str):
        """Invia messaggio via endpoint streaming /chat"""
        self.update_status("🔄 Invio messaggio (streaming)...")
        
        try:
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            accumulated_content = ""
            streaming_started = False
            
            async with self.http_client.stream(
                "POST",
                f"{self.api_base_url}/chat",
                json=payload
            ) as response:
                
                if response.status_code != 200:
                    error_msg = f"HTTP {response.status_code}: {await response.aread()}"
                    self.log_message("🔴 Errore", error_msg, is_error=True)
                    self.update_status("❌ Errore streaming")
                    return
                
                # Parsing streaming events
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            event_data = json.loads(line[6:])  # Rimuovi "data: "
                            event_type = event_data.get("type")
                            
                            if event_type == "connection":
                                thread_id = event_data.get("thread_id")
                                if not self.session_id:
                                    self.session_id = thread_id
                                self.log_message("🔄 Sistema", f"Streaming connesso (Thread: {thread_id})", is_streaming=True)
                                
                            elif event_type == "start":
                                self.log_message("🔄 Sistema", "Elaborazione iniziata...", is_streaming=True)
                                # Inizia il messaggio streaming
                                self.start_streaming_message("🤖 AI (Stream)")
                                streaming_started = True
                                
                            elif event_type == "content":
                                chunk = event_data.get("chunk", "")
                                accumulated_content += chunk
                                # Aggiorna messaggio in tempo reale
                                if streaming_started:
                                    self.update_streaming_message("🤖 AI (Stream)", accumulated_content)
                                
                            elif event_type == "complete":
                                final_content = event_data.get("final_content", accumulated_content)
                                total_chunks = event_data.get("total_chunks", 0)
                                # Finalizza messaggio streaming
                                if streaming_started:
                                    self.finalize_streaming_message(
                                        "🤖 AI (Stream)", 
                                        final_content, 
                                        f"[{total_chunks} chunks]"
                                    )
                                else:
                                    # Fallback se non è mai partito lo streaming
                                    self.log_message("🤖 AI (Stream)", f"{final_content} [{total_chunks} chunks]")
                                
                                self.update_status("✅ Streaming completato")
                                
                            elif event_type == "error":
                                error_msg = event_data.get("error", "Errore sconosciuto")
                                self.log_message("🔴 Errore", f"Errore streaming: {error_msg}", is_error=True)
                                self.update_status("❌ Errore durante streaming")
                                
                            elif event_type == "done":
                                self.update_status("✅ Streaming terminato")
                                break
                                
                        except json.JSONDecodeError as e:
                            self.log_message("🔴 Errore", f"Errore parsing JSON: {e}", is_error=True)
                        except Exception as e:
                            self.log_message("🔴 Errore", f"Errore processing event: {e}", is_error=True)
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore streaming: {e}", is_error=True)
            self.update_status("❌ Errore connessione streaming")
    
    async def send_message(self, message: str):
        """Invia messaggio usando modalità appropriata"""
        if not message.strip():
            return
        
        self.log_message("Tu", message)
        
        if self.streaming_enabled:
            await self.send_message_streaming(message)
        else:
            await self.send_message_normal(message)
    
    async def action_send_message(self) -> None:
        """Azione per inviare messaggio (binding Enter)"""
        message_input = self.query_one("#message_input", Input)
        message = message_input.value

        if message.strip():
            message_input.value = ""  # Pulisce l'input
            try:
                # Timeout più lungo per streaming
                timeout = 30.0 if self.streaming_enabled else 10.0
                await asyncio.wait_for(self.send_message(message), timeout=timeout)
            except asyncio.TimeoutError:
                self.log_message("🔴 Sistema", "Timeout invio messaggio", is_error=True)
                self.update_status("❌ Timeout invio messaggio")
            except Exception as e:
                self.log_message("🔴 Sistema", f"Errore invio messaggio: {e}", is_error=True)
                self.update_status("❌ Errore invio messaggio")
    
    async def on_switch_changed(self, event) -> None:
        """Gestisce cambio stato switch streaming"""
        if event.switch.id == "streaming_switch":
            self.streaming_enabled = event.value
            mode = "Streaming" if self.streaming_enabled else "Normal"
            self.log_message("🟢 Sistema", f"Modalità cambiata: {mode}")
            
            status_mode = "Streaming ON" if self.streaming_enabled else "Normal Mode"
            self.update_status(f"🟢 Connesso | {status_mode} | Pronto per chattare")
    
    def action_toggle_streaming(self) -> None:
        """Toggle streaming mode (CTRL+S)"""
        switch = self.query_one("#streaming_switch", Switch)
        switch.value = not switch.value
        self.streaming_enabled = switch.value
        mode = "Streaming" if self.streaming_enabled else "Normal"
        self.log_message("🟢 Sistema", f"Modalità toggled: {mode}")
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Gestisce click sui bottoni"""
        if event.button.id == "send_button":
            await self.action_send_message()
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Gestisce invio messaggio da Input (Enter)"""
        if event.input.id == "message_input":
            await self.action_send_message()
    
    def action_clear_chat(self) -> None:
        """Pulisce la chat (CTRL+L)"""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.clear()
        self.log_message("🟢 Sistema", "Chat pulita")
        self.session_id = None  # Reset sessione

    async def shutdown(self):
        """Chiude risorse in modo sicuro"""
        if self.http_client:
            try:
                await self.http_client.aclose()
            except Exception as e:
                self.log_message("🔴 Sistema", f"Errore durante la chiusura HTTP: {e}", is_error=True)
        self.log_message("🟢 Sistema", "Applicazione terminata correttamente")
        await asyncio.sleep(0.1)  # permette al log di essere renderizzato


    def action_quit(self) -> None:
        """Termina l'applicazione in modo sicuro"""
        asyncio.create_task(self.shutdown())
        self.exit()

def main():
    """Funzione principale"""
    try:
        app = ChatClient()
        app.title = "SimpleChatApp Client v2.3"
        app.sub_title = "Chat con AI via REST API - Streaming Support"
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
