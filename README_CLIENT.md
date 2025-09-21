# SimpleChatApp Client

Un client chat minimale realizzato con Textual per interagire con l'API REST di SimpleChatApp.

## Installazione Dipendenze

```bash
pip install textual httpx
```

## Utilizzo

1. **Avvia il server SimpleChatApp:**
   ```bash
   python main.py
   ```
   Il server sarà disponibile su `http://localhost:8000`

2. **Avvia il client chat:**
   ```bash
   python client.py
   ```

## Funzionalità

- 💬 **Chat Interface**: Interfaccia pulita con area messaggi e campo input
- 🔗 **Connessione API**: Connessione automatica al server REST su localhost:8000
- 🤖 **Sessioni**: Gestione automatica delle sessioni di conversazione
- ⚡ **Controlli Rapidi**:
  - `Enter`: Invia messaggio
  - `CTRL+C` / `ESC`: Termina applicazione
  - `CTRL+L`: Pulisce la chat
- 📊 **Status Bar**: Mostra stato connessione e operazioni in corso
- 🎨 **Colori**: Messaggi colorati per distinguere utente, AI e sistema
- ⏰ **Timestamp**: Timestamp per ogni messaggio

## Interfaccia

```
┌─ SimpleChatApp Client ─────────────────────────────────┐
│                                                        │
│  ┌─ Chat Log ──────────────────────────────────────┐   │
│  │ [14:30:15] 🟢 Sistema: Connesso al server...    │   │
│  │ [14:30:20] Tu: Ciao, come stai?                 │   │
│  │ [14:30:21] 🤖 AI: Ciao! Sto bene, grazie...    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                        │
│  ┌─────────────────────────────────┐ ┌────────────┐    │
│  │ Scrivi il tuo messaggio qui...  │ │    Send    │    │
│  └─────────────────────────────────┘ └────────────┘    │
│                                                        │
│  🟢 Connesso | Pronto per chattare                     │
│                                                        │
│ CTRL+C Quit │ Enter Send │ CTRL+L Clear Chat           │
└────────────────────────────────────────────────────────┘
```

## Gestione Errori

Il client gestisce automaticamente:
- ❌ **Server non raggiungibile**: Mostra messaggio di errore
- ❌ **Errori HTTP**: Visualizza codici di stato e messaggi
- ❌ **Timeout**: Gestisce timeout delle richieste (30s)
- ❌ **Interruzioni**: Terminazione pulita con CTRL+C

## API Endpoint Utilizzati

- `GET /health`: Verifica stato server
- `POST /query`: Invia messaggi chat
  ```json
  {
    "query": "Il tuo messaggio",
    "session_id": "optional-session-id"
  }
  ```

## Risoluzione Problemi

### Server non raggiungibile
```
🔴 Server non raggiungibile
```
**Soluzione**: Verifica che il server sia avviato su `http://localhost:8000`

### Dipendenze mancanti
```
ModuleNotFoundError: No module named 'textual'
```
**Soluzione**: Installa le dipendenze:
```bash
pip install textual httpx
```

### Errori di connessione
- Verifica che il server sia attivo
- Controlla i log del server per errori
- Riavvia client e server se necessario

## Sviluppo

Il client è progettato per essere:
- **Minimale**: Interfaccia essenziale ma completa
- **Robusto**: Gestione errori completa
- **Intuitivo**: Controlli standard (Enter, CTRL+C, ESC)
- **Estensibile**: Facilmente modificabile per nuove funzionalità