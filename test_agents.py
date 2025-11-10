#!/usr/bin/env python3
"""
Test script for ingest_news and score_news agents
Uruchamia oba agenty równolegle i wyświetla logi.
"""

import asyncio
import sys
import os

# Dodaj ścieżki do sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agents/ingest_news'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'agents/score_news'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'packages'))

from agents.ingest_news.main import IngestNewsAgent
from agents.score_news.main import ScoreNewsAgent


async def main():
    """Uruchom oba agenty równolegle"""

    print("="* 80)
    print(" AI Portfolio Manager - Agents Test ")
    print("="* 80)
    print("\nStarting ingest_news and score_news agents...")
    print("Press Ctrl+C to stop\n")

    # Utwórz oba agenty
    ingest_agent = IngestNewsAgent()
    score_agent = ScoreNewsAgent()

    # Uruchom oba agenty równolegle
    try:
        await asyncio.gather(
            ingest_agent.run(),
            score_agent.run()
        )
    except KeyboardInterrupt:
        print("\n\n" + "="*80)
        print(" Test completed - agents stopped ")
        print("="*80)


if __name__ == "__main__":
    # Ensure we have .env file
    if not os.path.exists('.env'):
        print("⚠️  Warning: .env file not found. Copy .env.example to .env and configure.")
        print("Using default configuration...\n")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
