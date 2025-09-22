#!/usr/bin/env python3
"""
client_session_manager.py - Chat Client con Gestione Sessioni Avanzata
=====================================================================

Client Textual con:
- Gestione sessioni multiple
- Creazione/switching sessioni
- Memoria persistente per sessione
- Interfaccia per gestione sessioni

Installazione richiesta:
    pip install textual httpx rich

Uso:
    python client_session_manager.py
"""

import asyncio
import sys
import json
from datetime import datetime
from typing import Optional, Dict

import httpx
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, Switch, Select
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel


class SessionManagerClient(App):
    """Client chat con gestione sessioni avanzata"""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #chat_log {
        height: 1fr;
        border: solid $accent;
        margin: 1;
    }
    
    #session_controls {
        height: 3;
        border: solid $warning;
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
        ("ctrl+n", "new_session", "New Session"),
    ]
    
    def __init__(self):
        super().__init__()
        self.api_base_url = "http://localhost:8000"
        self.current_session_id: Optional[str] = None
        self.sessions: Dict[str, Dict] = {}  # session_id -> {name, created_at, message_count}
        self.http_client: Optional[httpx.AsyncClient] = None
        
    def compose(self) -> ComposeResult:
        """Costruisce l'interfaccia utente"""
        yield Header()
        
        # Area controlli sessione
        yield Container(
            Horizontal(
                Button("Nuova Sessione", variant="success", id="new_session_btn"),
                Select(
                    [("Nessuna sessione", None)],
                    id="session_select",
                    allow_blank=False
                ),
                Button("Info Sessione", variant="default", id="info_session_btn"),
                Button("Elimina", variant="error", id="delete_session_btn"),
            ),
            id="session_controls"
        )
        
        # Chat log
        yield RichLog(id="chat_log", highlight=True, markup=True)
        
        # Input area
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
        
        yield Static("🎛️ Session Manager Client | CTRL+N=Nuova Sessione", id="status_bar")
        yield Footer()
    
    async def on_mount(self) -> None:
        """Inizializzazione all'avvio"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Test connessione
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                self.log_message("🟢 Sistema", "Connesso al server SimpleChatApp")
                self.update_status("🟢 Connesso | Pronto per creare sessioni")
            else:
                self.log_message("🔴 Sistema", f"Server errore: {response.status_code}")
        except Exception as e:
            self.log_message("🔴 Sistema", f"Connessione fallita: {e}")
        
        # Focus input
        self.query_one("#message_input").focus()
    
    def log_message(self, sender: str, message: str, is_error: bool = False):
        """Aggiunge messaggio al log principale"""
        chat_log = self.query_one("#chat_log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if is_error:
            color = "red"
        elif "Sistema" in sender:
            color = "green" if "🟢" in sender else "red"
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
    
    async def create_new_session(self, session_name: str = None):
        """Crea una nuova sessione"""
        try:
            response = await self.http_client.post(f"{self.api_base_url}/session/new")
            if response.status_code == 200:
                data = response.json()
                session_id = data["session_id"]
                
                # Nome sessione
                if not session_name:
                    session_count = len(self.sessions) + 1
                    session_name = f"Sessione {session_count}"
                
                # Memorizza sessione
                self.sessions[session_id] = {
                    "name": session_name,
                    "created_at": datetime.now(),
                    "message_count": 0
                }
                
                # Aggiorna interfaccia
                await self.update_session_select()
                await self.switch_to_session(session_id)
                
                self.log_message("🆕 Sessione", f"Creata: {session_name} ({session_id[:12]}...)")
                
                return session_id
            else:
                self.log_message("🔴 Errore", f"Creazione sessione fallita: {response.status_code}")
                return None
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore creazione sessione: {e}")
            return None
    
    async def update_session_select(self):
        """Aggiorna dropdown sessioni"""
        session_select = self.query_one("#session_select", Select)
        
        options = []
        if not self.sessions:
            options = [("Nessuna sessione", None)]
        else:
            for session_id, session_data in self.sessions.items():
                name = session_data["name"]
                short_id = session_id[:8]
                msg_count = session_data["message_count"]
                display_name = f"{name} ({short_id}...) [{msg_count} msg]"
                options.append((display_name, session_id))
        
        session_select.set_options(options)
        
        # Seleziona sessione corrente
        if self.current_session_id:
            session_select.value = self.current_session_id
    
    async def switch_to_session(self, session_id: str):
        """Cambia alla sessione specificata"""
        if session_id in self.sessions:
            self.current_session_id = session_id
            session_name = self.sessions[session_id]["name"]
            self.update_status(f"📱 Sessione Attiva: {session_name}")
            self.log_message("🔄 Switch", f"Passato a: {session_name}")
        else:
            self.log_message("🔴 Errore", f"Sessione {session_id} non trovata")
    
    async def get_session_info(self, session_id: str):
        """Ottieni informazioni su sessione"""
        try:
            response = await self.http_client.get(f"{self.api_base_url}/session/{session_id}/info")
            if response.status_code == 200:
                data = response.json()
                return data
            else:
                self.log_message("🔴 Errore", f"Info sessione fallita: {response.status_code}")
                return None
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore info sessione: {e}")
            return None
    
    async def delete_session(self, session_id: str):
        """Elimina sessione"""
        try:
            response = await self.http_client.delete(f"{self.api_base_url}/conversation/{session_id}")
            if response.status_code == 200:
                session_name = self.sessions[session_id]["name"]
                del self.sessions[session_id]
                
                # Se era la sessione corrente, deseleziona
                if self.current_session_id == session_id:
                    self.current_session_id = None
                    self.update_status("🟢 Connesso | Nessuna sessione attiva")
                
                await self.update_session_select()
                self.log_message("🗑️ Elimina", f"Sessione eliminata: {session_name}")
                return True
            else:
                self.log_message("🔴 Errore", f"Eliminazione fallita: {response.status_code}")
                return False
        except Exception as e:
            self.log_message("🔴 Errore", f"Errore eliminazione: {e}")
            return False
    
    async def send_message(self, message: str):
        """Invia messaggio"""
        if not self.current_session_id:
            self.log_message("⚠️ Warning", "Nessuna sessione attiva! Crea una sessione prima.")
            return
        
        if not message.strip():
            return
        
        self.log_message("Tu", message)
        
        try:
            payload = {
                "query": message,
                "session_id": self.current_session_id
            }
            
            response = await self.http_client.post(
                f"{self.api_base_url}/query",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", "Nessuna risposta")
                doc_count = data.get("document_count", 0)
                
                ai_message = f"{result}"
                if doc_count > 0:
                    ai_message += f" ({doc_count} documenti)"
                
                self.log_message("🤖 AI", ai_message)
                
                # Aggiorna contatore messaggi
                if self.current_session_id in self.sessions:
                    self.sessions[self.current_session_id]["message_count"] += 2  # User + AI
                    await self.update_session_select()
                
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
                error_msg = error_data.get("message", error_data.get("detail", "Errore sconosciuto"))
                self.log_message("🔴 Errore", f"HTTP {response.status_code}: {error_msg}", is_error=True)
                
        except Exception as e:
            self.log_message("🔴 Errore", f"Invio: {e}", is_error=True)
    
    async def action_send_message(self) -> None:
        """Azione invio messaggio"""
        message_input = self.query_one("#message_input", Input)
        message = message_input.value

        if message.strip():
            message_input.value = ""
            await self.send_message(message)
    
    async def action_new_session(self) -> None:
        """Crea nuova sessione (CTRL+N)"""
        await self.create_new_session()
    
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Click bottoni"""
        if event.button.id == "send_button":
            await self.action_send_message()
        elif event.button.id == "new_session_btn":
            await self.create_new_session()
        elif event.button.id == "info_session_btn":
            if self.current_session_id:
                info = await self.get_session_info(self.current_session_id)
                if info:
                    session_name = self.sessions[self.current_session_id]["name"]
                    total_messages = info.get("total_messages", 0)
                    self.log_message("📊 Info", f"{session_name}: {total_messages} messaggi totali")
            else:
                self.log_message("⚠️ Warning", "Nessuna sessione selezionata")
        elif event.button.id == "delete_session_btn":
            if self.current_session_id:
                await self.delete_session(self.current_session_id)
            else:
                self.log_message("⚠️ Warning", "Nessuna sessione da eliminare")
    
    async def on_select_changed(self, event: Select.Changed) -> None:
        """Cambio selezione sessione"""
        if event.select.id == "session_select" and event.value:
            await self.switch_to_session(event.value)
    
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter su input"""
        if event.input.id == "message_input":
            await self.action_send_message()
    
    def action_clear_chat(self) -> None:
        """Pulisce chat (CTRL+L)"""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.clear()
        self.log_message("🟢 Sistema", "Chat pulita (memoria sessione mantenuta)")

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
        app = SessionManagerClient()
        app.title = "SimpleChatApp Session Manager v4.0"
        app.sub_title = "Multi-Session Chat with Memory Management"
        app.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Errore fatale: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
