#!/usr/bin/env python3
"""
client_console.py - Fast Console Streaming Client (FIXED)
========================================================

Client console semplice e veloce con input funzionante.
Avvio rapido, nessuna GUI, solo console pura.

Installazione richiesta:
    pip install rich httpx

Uso:
    python client_console.py
"""

import asyncio
import json
import sys
from datetime import datetime
from typing import Optional

import httpx
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.align import Align


class ConsoleStreamingClient:
    """Client console veloce per streaming"""
    
    def __init__(self):
        self.console = Console()
        self.api_base_url = "http://localhost:8000"
        self.session_id: Optional[str] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        self.streaming_enabled = True
        
        # State
        self.current_response = ""
        self.is_streaming = False
        
    def print_header(self):
        """Stampa header una volta"""
        self.console.clear()
        header = Panel(
            Align.center(
                Text("🤖 SimpleChatApp Console Client", style="bold blue")
            ),
            style="blue"
        )
        self.console.print(header)
        self.console.print()
        
        # Info comandi
        self.console.print(
            "[dim]Comandi: 'quit'=esci | 'clear'=pulisci | 'toggle'=cambia modalità[/]"
        )
        self.console.print()
    
    async def connect(self) -> bool:
        """Connessione al server"""
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        try:
            response = await self.http_client.get(f"{self.api_base_url}/health")
            if response.status_code == 200:
                self.console.print("✅ [green]Connesso al server[/]")
                return True
            else:
                self.console.print(f"❌ [red]Server errore: {response.status_code}[/]")
                return False
        except Exception as e:
            self.console.print(f"❌ [red]Connessione fallita: {e}[/]")
            return False
    
    async def send_streaming(self, message: str):
        """Invio con streaming console"""
        self.current_response = ""
        self.is_streaming = True
        
        # Mostra messaggio utente
        self.console.print(f"[bold blue]Tu:[/] {message}")
        
        try:
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            # Panel per streaming response
            streaming_panel = Panel(
                Text("💭 AI sta pensando...", style="italic"),
                title="🤖 AI Response",
                border_style="green"
            )
            
            with Live(streaming_panel, console=self.console, refresh_per_second=5) as live:
                
                async with self.http_client.stream(
                    "POST",
                    f"{self.api_base_url}/chat",
                    json=payload
                ) as response:
                    
                    if response.status_code != 200:
                        error_text = await response.aread()
                        self.console.print(f"[red]❌ HTTP {response.status_code}: {error_text}[/]")
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                event_data = json.loads(line[6:])
                                event_type = event_data.get("type")
                                
                                if event_type == "connection":
                                    thread_id = event_data.get("thread_id")
                                    if not self.session_id:
                                        self.session_id = thread_id
                                
                                elif event_type == "content":
                                    chunk = event_data.get("chunk", "")
                                    self.current_response += chunk
                                    
                                    # Update live display con word wrap
                                    wrapped_text = self._wrap_text(self.current_response, 70)
                                    content = Text(wrapped_text)
                                    content.append(" ▋", style="blink yellow")  # Cursore
                                    
                                    live.update(Panel(
                                        content,
                                        title="🤖 AI Response (Streaming)",
                                        border_style="green"
                                    ))
                                
                                elif event_type == "complete":
                                    final_content = event_data.get("final_content", self.current_response)
                                    total_chunks = event_data.get("total_chunks", 0)
                                    
                                    # Final display
                                    wrapped_final = self._wrap_text(final_content, 70)
                                    final_text = Text(wrapped_final)
                                    
                                    live.update(Panel(
                                        final_text,
                                        title=f"🤖 AI Response [Completed - {total_chunks} chunks]",
                                        border_style="blue"
                                    ))
                                    break
                                    
                                elif event_type == "error":
                                    error_msg = event_data.get("error", "Errore sconosciuto")
                                    live.update(Panel(
                                        Text(f"❌ Errore: {error_msg}", style="red"),
                                        title="🤖 AI Response",
                                        border_style="red"
                                    ))
                                    break
                                    
                            except json.JSONDecodeError:
                                continue
                
        except Exception as e:
            self.console.print(f"[red]❌ Errore streaming: {e}[/]")
        finally:
            self.is_streaming = False
            self.console.print()  # Spazio dopo risposta
    
    async def send_normal(self, message: str):
        """Invio normale"""
        self.console.print(f"[bold blue]Tu:[/] {message}")
        
        try:
            payload = {
                "query": message,
                "session_id": self.session_id
            }
            
            with self.console.status("[yellow]Elaborazione...[/]", spinner="dots"):
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
                
                # Display response
                ai_message = result
                if doc_count > 0:
                    ai_message += f" ({doc_count} documenti)"
                
                wrapped_response = self._wrap_text(ai_message, 70)
                
                self.console.print(Panel(
                    wrapped_response,
                    title="🤖 AI Response",
                    border_style="blue"
                ))
                
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
                error_msg = error_data.get("message", error_data.get("detail", "Errore sconosciuto"))
                self.console.print(f"[red]❌ HTTP {response.status_code}: {error_msg}[/]")
                
        except Exception as e:
            self.console.print(f"[red]❌ Errore: {e}[/]")
        
        self.console.print()  # Spazio
    
    def _wrap_text(self, text: str, width: int) -> str:
        """Word wrap semplice"""
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line + " " + word) > width and current_line:
                lines.append(current_line)
                current_line = word
            else:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return "\\n".join(lines)
    
    def get_input(self) -> str:
        """Input semplice e funzionante"""
        mode_indicator = "🔄 STREAM" if self.streaming_enabled else "📡 NORMAL"
        session_info = f" | Session: {self.session_id[:8] if self.session_id else 'None'}"
        
        try:
            prompt = f"[bold green]{mode_indicator}[/]{session_info}\\n[bold cyan]❯[/] "
            return self.console.input(prompt)
        except (KeyboardInterrupt, EOFError):
            return "quit"
    
    async def run(self):
        """Main loop semplice e veloce"""
        self.print_header()
        
        # Connessione
        if not await self.connect():
            self.console.print("[red]Impossibile connettersi. Uscita.[/]")
            return
        
        self.console.print("[green]✅ Ready! Inizia a chattare...[/]")
        self.console.print()
        
        try:
            while True:
                # Input bloccante ma funzionante
                user_input = self.get_input()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                elif user_input.lower() == 'clear':
                    self.print_header()
                    self.console.print("[green]✅ Chat pulita[/]")
                    continue
                elif user_input.lower() == 'toggle':
                    self.streaming_enabled = not self.streaming_enabled
                    mode = "Streaming" if self.streaming_enabled else "Normal"
                    self.console.print(f"[yellow]🔄 Modalità: {mode}[/]")
                    continue
                elif user_input.strip() == '':
                    continue
                
                # Invia messaggio
                if self.streaming_enabled:
                    await self.send_streaming(user_input)
                else:
                    await self.send_normal(user_input)
        
        except KeyboardInterrupt:
            pass
        finally:
            if self.http_client:
                await self.http_client.aclose()
            self.console.print("\\n[yellow]👋 Arrivederci![/]")


def main():
    """Entry point veloce"""
    client = ConsoleStreamingClient()
    
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\\n👋 Bye!")


if __name__ == "__main__":
    main()
