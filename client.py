#!/usr/bin/env python3
"""
client.py - Textual Chat Client for SimpleChatApp
=================================================

Un client chat minimale che utilizza Textual per interagire con l'API REST.
Supporta terminazione tramite CTRL+C o ESC.

Installazione richiesta:
    pip install textual httpx

Uso:
    python client.py
"""

import asyncio
import sys
from datetime import datetime
from typing import Optional

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static
from textual.binding import Binding
from rich.text import Text
from rich.panel import Panel


class ChatClient(App):
    """Client chat Textual per SimpleChatApp API"""
    
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
        height: 3;
        dock: bottom;
    }
    
    #message_input {
        width: 1fr;
        margin: 0 1;
    }
    
    #send_button {
        width: 10;
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
    ]
    
    def __init__(self):
        super().__init__()
        self.api_base_url = "http://localhost:8000"
        self.session_id: Optional[str] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        
    def compose(self) -> ComposeResult:
        """Costruisce l'interfaccia utente"""
        yield Header()
        yield Container(
            RichLog(id="chat_log", highlight=True, markup=True),
            id="main_container"
        )
        yield Container(
            Horizontal(
                Input(
                    placeholder="Scrivi il tuo messaggio qui...", 
                    id="message_input"
                ),
                Button("Send", variant="primary", id="send_button"),
            ),
            id="input_container"
        )
        yield Static("🔗 Connesso a http://localhost:8000 | ESC/CTRL+C per uscire", id="status_bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Inizializzazione all'avvio"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Test connessione API
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                self.log_message("🟢 Sistema", "Connesso al server SimpleChatApp")
                self.update_status("🟢 Connesso | Pronto per chattare")
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
    
    def log_message(self, sender: str, message: str, is_error: bool = False):
        """Aggiunge un messaggio al log della chat"""
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
        
        # Crea il messaggio formattato
        text = Text()
        text.append(f"[{timestamp}] ", style="dim")
        text.append(f"{sender}: ", style=f"bold {color}")
        text.append(message)
        
        chat_log.write(text)
    
    def update_status(self, status: str):
        """Aggiorna la barra di stato"""
        status_bar = self.query_one("#status_bar", Static)
        status_bar.update(status)
    
    async def send_message(self, message: str):
        """Invia un messaggio all'API"""
        if not message.strip():
            return
        
        self.log_message("Tu", message)
        self.update_status("📡 Invio messaggio...")
        
        try:
            # Prepara la richiesta
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            # Invia alla API
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
                
                self.log_message("🤖 AI", ai_message)
                self.update_status("✅ Messaggio inviato")
                
            else:
                error_msg = f"Errore HTTP {response.status_code}: {response.text}"
                self.log_message("🔴 Errore", error_msg, is_error=True)
                self.update_status("❌ Errore nella richiesta")
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore di connessione: {e}", is_error=True)
            self.update_status("❌ Errore di connessione")
    
    async def action_send_message(self) -> None:
        """Azione per inviare messaggio (binding Enter)"""
        message_input = self.query_one("#message_input", Input)
        message = message_input.value

        if message.strip():
            message_input.value = ""  # Pulisce l'input
            try:
                # Invia il messaggio con timeout di 5 secondi
                await asyncio.wait_for(self.send_message(message), timeout=5.0)
            except asyncio.TimeoutError:
                self.log_message("🔴 Sistema", "Timeout invio messaggio", is_error=True)
                self.update_status("❌ Timeout invio messaggio")
            except Exception as e:
                self.log_message("🔴 Sistema", f"Errore invio messaggio: {e}", is_error=True)
                self.update_status("❌ Errore invio messaggio")
        
        if message.strip():
            message_input.value = ""  # Pulisce l'input
            await self.send_message(message)
    
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
        app.title = "SimpleChatApp Client"
        app.sub_title = "Chat con AI via REST API"
        app.run()
    except KeyboardInterrupt:
        pass

    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()