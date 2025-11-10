# AI Portfolio Manager 🤖📈

AI-powered portfolio manager dla handlu akcjami USA. System oparty na architekturze mikroserwisowej z autonomicznymi agentami komunikującymi się przez Redis Streams.

## 🎯 Funkcjonalności

- **Automatyczne pobieranie wiadomości** - RSS, News API, social media
- **Analiza sentymentu AI** - Scoring wiadomości przy użyciu LLM (OpenAI/Anthropic)
- **Dane rynkowe real-time** - Integracja z Alpha Vantage, Polygon.io, IEX Cloud
- **Generowanie sygnałów handlowych** - Strategia oparta na analizie technicznej + sentymencie
- **Zarządzanie ryzykiem** - Automatyczna ocena i approval sygnałów
- **Automatyczne wykonanie** - Integracja z brokerami (Alpaca, Interactive Brokers)
- **Detekcja anomalii** - Shock detector dla nagłych wydarzeń rynkowych
- **Dashboard UI** - Real-time monitoring portfela i sygnałów
- **REST API** - Dostęp do danych i kontrola systemu

## 🏗️ Architektura

System składa się z 7 autonomicznych agentów komunikujących się przez Redis Streams:

```
┌─────────────────┐
│  Ingest News    │──┐
└─────────────────┘  │
                     ▼
                ┌─────────────┐      ┌─────────────────┐
                │ Score News  │      │  Market Data    │
                └─────────────┘      └─────────────────┘
                     │                       │
                     └───────────┬───────────┘
                                 ▼
                          ┌─────────────┐
                          │  Strategy   │
                          └─────────────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │    Risk     │
                          └─────────────┘
                                 │
                                 ▼
                          ┌─────────────┐
                          │  Execution  │
                          └─────────────┘

┌─────────────────┐
│ Shock Detector  │ (monitors market data)
└─────────────────┘
```

### Agenty

| Agent | Rola | Input Stream | Output Stream |
|-------|------|--------------|---------------|
| **ingest_news** | Pobiera wiadomości finansowe | - | `news:raw` |
| **score_news** | Ocenia sentyment wiadomości | `news:raw` | `news:scored` |
| **market_data** | Pobiera dane rynkowe | - | `market:data` |
| **strategy** | Generuje sygnały handlowe | `market:data`, `news:scored` | `signals:trading` |
| **risk** | Zarządza ryzykiem | `signals:trading` | `signals:approved` |
| **execution** | Wykonuje transakcje | `signals:approved` | `executions:completed` |
| **shock_detector** | Wykrywa anomalie | `market:data` | `alerts:shocks` |

## 📁 Struktura projektu

```
ClaudeBrokerAI/
├── agents/                      # Autonomiczne agenty
│   ├── ingest_news/            # Pobieranie wiadomości
│   ├── score_news/             # Scoring sentymentu
│   ├── market_data/            # Dane rynkowe
│   ├── strategy/               # Generowanie sygnałów
│   ├── risk/                   # Zarządzanie ryzykiem
│   ├── execution/              # Wykonanie transakcji
│   └── shock_detector/         # Detekcja anomalii
├── apps/
│   ├── api/                    # FastAPI REST API
│   └── ui/                     # React/Next.js dashboard
├── packages/
│   └── common/                 # Współdzielone typy i utilities
│       ├── schemas.py          # JSON schemas (Pydantic)
│       └── redis_utils.py      # Helper functions
├── infra/                      # Infrastructure as Code
│   ├── Dockerfile.agent
│   ├── Dockerfile.api
│   └── README.md
├── docker-compose.yml          # Orkiestracja wszystkich serwisów
├── .env.example                # Przykładowa konfiguracja
└── README.md
```

## 🚀 Quick Start

### Wymagania

- Docker & Docker Compose
- Python 3.11+ (dla development lokalnego)
- API keys (opcjonalne dla rozwoju):
  - OpenAI / Anthropic (do scoringu wiadomości)
  - Alpha Vantage / Polygon.io (dane rynkowe)
  - Alpaca (broker - papierowy handel)

### Instalacja

1. **Sklonuj repozytorium**
```bash
git clone <repository-url>
cd ClaudeBrokerAI
```

2. **Konfiguracja środowiska**
```bash
cp .env.example .env
# Edytuj .env i dodaj swoje API keys
```

3. **Uruchom wszystkie serwisy**
```bash
docker-compose up --build
```

4. **Sprawdź status**
```bash
# API
curl http://localhost:8000

# Redis
docker-compose exec redis redis-cli ping

# Logi agentów
docker-compose logs -f agent-strategy
```

### Development lokalny (bez Docker)

```bash
# Zainstaluj dependencies
pip install -r packages/common/requirements.txt
pip install redis pydantic openai anthropic python-dotenv

# Uruchom tylko Redis
docker-compose up redis

# Uruchom agenta lokalnie
cd agents/market_data
python main.py
```

## 📊 API Endpoints

REST API dostępne na `http://localhost:8000`:

- `GET /` - Health check
- `GET /api/v1/signals` - Najnowsze sygnały handlowe
- `GET /api/v1/portfolio` - Statystyki portfela
- `GET /api/v1/positions` - Aktualne pozycje
- `GET /api/v1/alerts` - Alerty o anomaliach rynkowych

Dokumentacja interaktywna: `http://localhost:8000/docs`

## 🔧 Konfiguracja

### Redis Streams

Wszystkie agenty komunikują się przez Redis Streams. Nazwy streamów zdefiniowane w `packages/common/schemas.py`:

- `news:raw` - Surowe wiadomości
- `news:scored` - Ocenione wiadomości
- `market:data` - Dane rynkowe
- `signals:trading` - Sygnały handlowe
- `signals:approved` - Zatwierdzone sygnały
- `executions:completed` - Wykonane transakcje
- `alerts:shocks` - Alerty anomalii

### Parametry ryzyka

Edytuj w `.env`:
```bash
MAX_POSITION_SIZE=10000          # Maksymalny rozmiar pojedynczej pozycji (USD)
MAX_PORTFOLIO_RISK=0.02          # Maksymalne ryzyko portfela (2%)
MIN_SIGNAL_CONFIDENCE=0.6        # Minimalna pewność sygnału
```

## 🧪 Testing

```bash
# Ręczne testowanie komunikacji między agentami
docker-compose exec redis redis-cli

# Sprawdź streamy
XINFO STREAM news:raw

# Czytaj wiadomości
XREAD COUNT 10 STREAMS market:data 0

# Monitoruj wszystkie operacje
MONITOR
```

## 📈 Roadmap

### Faza 1: MVP (Current)
- [x] Podstawowa struktura agentów
- [x] Redis Streams komunikacja
- [x] Docker orchestration
- [ ] Implementacja data sources (Alpha Vantage, News API)
- [ ] Podstawowa strategia handlowa
- [ ] Paper trading z Alpaca

### Faza 2: AI Enhancement
- [ ] LLM-based news scoring (GPT-4, Claude)
- [ ] Advanced sentiment analysis
- [ ] Machine learning dla strategy
- [ ] Backtesting framework
- [ ] Performance analytics

### Faza 3: Production
- [ ] Database (PostgreSQL) dla historycznych danych
- [ ] WebSocket real-time updates
- [ ] React dashboard z chartami
- [ ] Alert system (email, Telegram)
- [ ] Multi-broker support
- [ ] Risk monitoring dashboard

### Faza 4: Advanced Features
- [ ] Options trading
- [ ] Portfolio rebalancing
- [ ] Tax optimization
- [ ] Multi-strategy support
- [ ] ML model auto-tuning
- [ ] A/B testing strategies

## 🛡️ Security

⚠️ **WAŻNE**:
- Nigdy nie commituj `.env` z prawdziwymi API keys
- Używaj paper trading dla testów
- Regularnie backupuj dane portfela
- Monitoruj logi pod kątem anomalii

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📝 License

MIT License - see LICENSE file

## 🙋 Support

- Issues: [GitHub Issues](https://github.com/your-org/ClaudeBrokerAI/issues)
- Documentation: [Wiki](https://github.com/your-org/ClaudeBrokerAI/wiki)
- Discord: [Join our community](https://discord.gg/your-server)

## ⚠️ Disclaimer

Ten projekt jest przeznaczony wyłącznie do celów edukacyjnych i badawczych. Handel akcjami wiąże się z ryzykiem finansowym. Autor nie ponosi odpowiedzialności za straty poniesione w wyniku użycia tego oprogramowania. Zawsze przeprowadź własne badania i konsultuj się z doradcą finansowym przed podejmowaniem decyzji inwestycyjnych.

**USE AT YOUR OWN RISK** 🚨

---

Made with ❤️ by AI Portfolio Manager Team
