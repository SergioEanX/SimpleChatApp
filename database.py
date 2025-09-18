"""
database.py - MongoDB Service
=============================

Servizio per operazioni MongoDB async con Motor.
Gestisce connessioni, query execution e schema discovery.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from typing import List, Dict, Any
import asyncio


class MongoDBService:
    """
    Servizio MongoDB asincrono

    Gestisce:
    - Connessioni async con Motor
    - Esecuzione query MongoDB
    - Analisi schema collezioni
    - Error handling e cleanup
    """

    def __init__(self, uri: str, database_name: str):
        """
        Inizializza servizio MongoDB

        Args:
            uri: Connection string MongoDB (con auth se necessario)
            database_name: Nome del database da utilizzare
        """
        self.uri = uri
        self.database_name = database_name
        self.client: AsyncIOMotorClient = None
        self.db = None

    async def connect(self) -> None:
        """Stabilisce connessione asincrona al database"""
        if not self.client:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.database_name]

    async def close(self) -> None:
        """Chiude connessione database"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    async def test_connection(self) -> bool:
        """
        Testa connessione al database

        Returns:
            True se connessione ok, False altrimenti
        """
        try:
            await self.connect()
            # Ping per verificare connessione
            await self.client.admin.command('ping')
            print("✅ MongoDB ping successful")
            return True
        except ConnectionFailure as e:
            print(f"❌ MongoDB connection failed: {e}")
            return False
        except Exception as e:
            print(f"❌ MongoDB error: {e}")
            return False

    async def execute_query(self, collection: str, query: Dict[str, Any]) -> List[Dict]:
        """
        Esegue query MongoDB e restituisce documenti

        Args:
            collection: Nome collezione
            query: Query MongoDB in formato dict

        Returns:
            Lista documenti trovati

        Raises:
            Exception: Se query fallisce
        """
        await self.connect()

        try:
            coll = self.db[collection]

            # Gestisce operazioni speciali (sort, limit, etc.)
            if any(key.startswith('$') for key in query.keys()):
                cursor = await self._handle_aggregation(coll, query)
            else:
                # Query semplice
                cursor = coll.find(query)

            # Limita risultati per sicurezza
            cursor = cursor.limit(1000)

            # Converti risultati e gestisci ObjectId
            documents = []
            async for doc in cursor:
                # Converti ObjectId in string per serializzazione JSON
                if '_id' in doc:
                    doc['_id'] = str(doc['_id'])
                documents.append(doc)

            print(f"📊 Query eseguita: {len(documents)} documenti trovati")
            return documents

        except Exception as e:
            error_msg = f"Errore esecuzione query MongoDB: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    async def _handle_aggregation(self, collection, query: Dict[str, Any]):
        """
        Gestisce operazioni speciali come $sort, $limit

        Args:
            collection: Collezione MongoDB
            query: Query con operatori speciali

        Returns:
            Cursor risultato
        """
        # Estrae operatori speciali
        sort_spec = query.pop('$sort', None)
        limit_spec = query.pop('$limit', None)

        # Inizia con find base
        cursor = collection.find(query) if query else collection.find({})

        # Applica sort se presente
        if sort_spec:
            # Converte in formato MongoDB: {"campo": 1} -> [("campo", 1)]
            sort_list = [(field, direction) for field, direction in sort_spec.items()]
            cursor = cursor.sort(sort_list)

        # Applica limit se presente
        if limit_spec:
            cursor = cursor.limit(limit_spec)

        return cursor

    async def get_collection_schema(self, collection: str) -> Dict[str, Any]:
        """
        Analizza schema della collezione esaminando documenti campione

        Args:
            collection: Nome collezione da analizzare

        Returns:
            Dict con struttura schema della collezione

        Raises:
            Exception: Se analisi fallisce
        """
        await self.connect()

        try:
            coll = self.db[collection]

            # Campiona primi 3 documenti per dedurre schema
            sample_docs = []
            async for doc in coll.find().limit(3):
                # Rimuovi _id per schema più pulito
                doc.pop('_id', None)
                sample_docs.append(doc)

            if not sample_docs:
                print(f"⚠️ Collezione {collection} vuota")
                return {}

            # Analizza campi e tipi
            schema = self._analyze_schema(sample_docs)

            print(f"📋 Schema {collection}: {len(schema)} campi identificati")
            return schema

        except Exception as e:
            error_msg = f"Errore analisi schema: {str(e)}"
            print(f"❌ {error_msg}")
            raise Exception(error_msg)

    def _analyze_schema(self, documents: List[Dict]) -> Dict[str, Dict]:
        """
        Analizza documenti campione per estrarre schema

        Args:
            documents: Lista documenti da analizzare

        Returns:
            Schema con tipi e valori esempio
        """
        # Raccogli tutti i campi
        all_fields = set()
        for doc in documents:
            all_fields.update(doc.keys())

        schema = {}
        for field in sorted(all_fields):
            # Trova tipo più comune per questo campo
            field_types = []
            sample_values = []

            for doc in documents:
                if field in doc and doc[field] is not None:
                    field_types.append(type(doc[field]).__name__)
                    sample_values.append(doc[field])

            if field_types:
                # Tipo più comune
                most_common_type = max(set(field_types), key=field_types.count)

                schema[field] = {
                    'type': most_common_type,
                    'sample': sample_values[0] if sample_values else None,
                    'found_in': len([doc for doc in documents if field in doc])
                }

        return schema

    async def health_check(self) -> bool:
        """
        Health check rapido

        Returns:
            True se servizio operativo
        """
        try:
            return await self.test_connection()
        except Exception:
            return False
