"""
Database utilities for impact memory storage
SQLite database for storing shock event attributions and learning from historical patterns.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import json


class ImpactMemoryDB:
    """Database dla przechowywania impact memory (shock events + attributions)"""

    def __init__(self, db_path: str = "impact_memory.db"):
        """
        Args:
            db_path: Ścieżka do pliku bazy danych SQLite
        """
        self.db_path = db_path
        self.conn = None
        self._init_database()

    def _init_database(self):
        """Inicjalizuj bazę danych i tabele"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Return rows as dicts

        cursor = self.conn.cursor()

        # Tabela dla impact memory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS impact_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL,
                shock_type TEXT NOT NULL,
                shock_detected_at TEXT NOT NULL,
                shock_price REAL NOT NULL,
                shock_z_score REAL,
                shock_volume_percentile REAL,
                shock_severity REAL,
                cause_type TEXT,
                cause_text TEXT,
                cause_source TEXT,
                confidence REAL,
                impact_strength REAL,
                time_delta_minutes REAL,
                decay_profile TEXT,
                attributed_at TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)

        # Index dla szybszego wyszukiwania
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ticker_datetime
            ON impact_memory(ticker, shock_detected_at)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cause_type
            ON impact_memory(cause_type)
        """)

        self.conn.commit()
        print(f"[ImpactMemoryDB] Database initialized: {self.db_path}")

    def insert_attribution(
        self,
        event_id: str,
        ticker: str,
        shock_type: str,
        shock_detected_at: str,
        shock_price: float,
        shock_z_score: Optional[float] = None,
        shock_volume_percentile: Optional[float] = None,
        shock_severity: Optional[float] = None,
        cause_type: Optional[str] = None,
        cause_text: Optional[str] = None,
        cause_source: Optional[str] = None,
        confidence: Optional[float] = None,
        impact_strength: Optional[float] = None,
        time_delta_minutes: Optional[float] = None,
        decay_profile: Optional[Dict[str, Any]] = None,
        attributed_at: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Wstaw nowy rekord impact attribution

        Returns:
            Row ID
        """
        cursor = self.conn.cursor()

        # Serialize JSON fields
        decay_profile_json = json.dumps(decay_profile) if decay_profile else None
        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT INTO impact_memory (
                event_id, ticker, shock_type, shock_detected_at, shock_price,
                shock_z_score, shock_volume_percentile, shock_severity,
                cause_type, cause_text, cause_source,
                confidence, impact_strength, time_delta_minutes,
                decay_profile, attributed_at, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_id, ticker, shock_type, shock_detected_at, shock_price,
            shock_z_score, shock_volume_percentile, shock_severity,
            cause_type, cause_text, cause_source,
            confidence, impact_strength, time_delta_minutes,
            decay_profile_json, attributed_at, metadata_json,
            datetime.now(timezone.utc).isoformat()
        ))

        self.conn.commit()
        return cursor.lastrowid

    def get_attribution(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Pobierz attribution po event_id"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM impact_memory WHERE event_id = ?
        """, (event_id,))

        row = cursor.fetchone()
        if row:
            result = dict(row)
            # Deserialize JSON fields
            if result.get('decay_profile'):
                result['decay_profile'] = json.loads(result['decay_profile'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            return result

        return None

    def get_attributions_by_ticker(
        self,
        ticker: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Pobierz ostatnie attributions dla tickera"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM impact_memory
            WHERE ticker = ?
            ORDER BY shock_detected_at DESC
            LIMIT ?
        """, (ticker, limit))

        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('decay_profile'):
                result['decay_profile'] = json.loads(result['decay_profile'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)

        return results

    def get_similar_events(
        self,
        ticker: str,
        shock_type: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Znajdź podobne wydarzenia historyczne"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM impact_memory
            WHERE ticker = ? AND shock_type = ?
            ORDER BY shock_detected_at DESC
            LIMIT ?
        """, (ticker, shock_type, limit))

        rows = cursor.fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('decay_profile'):
                result['decay_profile'] = json.loads(result['decay_profile'])
            if result.get('metadata'):
                result['metadata'] = json.loads(result['metadata'])
            results.append(result)

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Pobierz statystyki bazy danych"""
        cursor = self.conn.cursor()

        # Total records
        cursor.execute("SELECT COUNT(*) as total FROM impact_memory")
        total = cursor.fetchone()['total']

        # By shock type
        cursor.execute("""
            SELECT shock_type, COUNT(*) as count
            FROM impact_memory
            GROUP BY shock_type
        """)
        by_shock_type = {row['shock_type']: row['count'] for row in cursor.fetchall()}

        # By cause type
        cursor.execute("""
            SELECT cause_type, COUNT(*) as count
            FROM impact_memory
            WHERE cause_type IS NOT NULL
            GROUP BY cause_type
        """)
        by_cause_type = {row['cause_type']: row['count'] for row in cursor.fetchall()}

        # Average confidence
        cursor.execute("""
            SELECT AVG(confidence) as avg_confidence
            FROM impact_memory
            WHERE confidence IS NOT NULL
        """)
        avg_confidence = cursor.fetchone()['avg_confidence']

        return {
            "total_records": total,
            "by_shock_type": by_shock_type,
            "by_cause_type": by_cause_type,
            "avg_confidence": avg_confidence
        }

    def close(self):
        """Zamknij połączenie z bazą"""
        if self.conn:
            self.conn.close()
            print(f"[ImpactMemoryDB] Database closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
