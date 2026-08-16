fpl-ai-agent/
│
├── README.md
├── requirements.txt
├── .env
├── .env.example
├── .gitignore
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── constants.py
│
├── data/
│   └── raw/
│       └── 2026-27/
│           ├── bootstrap/
│           ├── fixtures/
│           ├── players/
│           ├── live/
│           └── managers/
│
├── src/
│   ├── __init__.py
│   ├── collectors/
│   │   ├── __init__.py
│   │   └── fpl_client.py
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── validators.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logger.py
│       └── retry.py
│
├── scripts/
│   ├── fetch_bootstrap.py
│   ├── fetch_fixtures.py
│   └── fetch_player_history.py
│
├── logs/
│   └── collector/
│
└── tests/
    ├── __init__.py
    └── collectors/