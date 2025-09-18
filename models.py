"""
models.py - Pydantic Models
===========================

Definisce i modelli Pydantic per request/response dell'API.
Mantiene la tipizzazione forte e la validazione dei dati.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, Union
from datetime import datetime


class QueryRequest(BaseModel):
    """
    Richiesta per eseguire query MongoDB in linguaggio naturale.
    """
    query: str = Field(
        ...,
        description="Richiesta in linguaggio naturale",
        examples=["trova tutti i documenti con età maggiore di 25"]
    )
    session_id: Optional[str] = Field(
        None,
        description="Thread ID per memoria conversazione (auto-generato se mancante)",
        examples=["thread_abc12345"]
    )
    collection: Optional[str] = Field(
        None,
        description="Nome collezione MongoDB (usa default se mancante)",
        examples=["users"]
    )


class QueryResponse(BaseModel):
    """
    Risposta dopo esecuzione query.
    """
    session_id: str = Field(
        ...,
        description="Thread ID della conversazione",
        examples=["thread_abc12345"]
    )
    result: Union[str, Dict] = Field(
        ...,
        description="Risultato query (JSON serializzato o messaggio informativo)",
        examples=["Nessun documento trovato", {"nome": "Mario", "età": 30}]
    )
    data_saved: bool = Field(
        ...,
        description="True se risultati salvati su file (troppo grandi per la response)",
        examples=[False, True]
    )
    file_path: Optional[str] = Field(
        None,
        description="Percorso file temporaneo se data_saved=True",
        examples=["/tmp/query_result.json"]
    )
    document_count: int = Field(
        ...,
        description="Numero documenti trovati",
        examples=[0, 12]
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp esecuzione query (UTC)",
        examples=["2025-09-17T13:45:00Z"]
    )


class ConversationMessage(BaseModel):
    """
    Messaggio nella storia della conversazione.
    """
    type: Literal["human", "ai"] = Field(
        ...,
        description="Tipo messaggio",
        examples=["human", "ai"]
    )
    content: str = Field(
        ...,
        description="Contenuto del messaggio",
        examples=["Cerca i clienti con più di 30 anni", "Ho trovato 12 documenti"]
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp creazione messaggio (UTC)",
        examples=["2025-09-17T13:45:00Z"]
    )


class HealthResponse(BaseModel):
    """
    Risposta health check.
    """
    status: Literal["healthy", "degraded", "unhealthy"] = Field(
        ...,
        description="Stato generale del sistema",
        examples=["healthy", "degraded", "unhealthy"]
    )
    services: Dict[str, str] = Field(
        ...,
        description="Stato specifico dei servizi",
        examples=[{"mongo": "ok", "llm": "ok"}]
    )
    config: Dict[str, str] = Field(
        ...,
        description="Configurazione attiva",
        examples=[{"env": "dev", "debug": "true"}]
    )
