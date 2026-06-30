                    Flutter App
                         │
                         ▼
                  FastAPI Backend
                         │
     ┌───────────────────┼───────────────────┐
     │                   │                   │
 Authentication      Business Logic      Real-Time Layer
     │                   │                   │
 Firebase         Wallet / Ride / Dock      MQTT
     │                   │                   │
     └────────────── PostgreSQL ─────────────┘
                         │
                       Redis



                       Flutter App
       │
       ▼
REST API
       │
       ▼
FastAPI Backend
       │
 ┌─────┼────────┐
 │     │        │
 ▼     ▼        ▼
Firebase PostgreSQL Redis
       │
       ▼
MQTT Broker