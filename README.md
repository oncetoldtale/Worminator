# Worminator

Worminator is a stream companion application for [OnceToldTale](https://twitch.tv/oncetoldtale).

It handles Twitch integration, raffle management, persistent user data, and a real-time browser overlay system for OBS. It is designed as a modular backend where different platforms and interfaces can interact with shared application features.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Configuration](#configuration)
3. [Contributing](#contributing)
4. [License](#license)

## Getting Started<a id="getting-started"></a>

### Requirements

- [Python 3.10+](https://www.python.org/)
- [PostgreSQL](https://www.postgresql.org/download/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Installation

Clone the repository:

```bash
git clone https://github.com/simsonas86/Worminator.git
cd Worminator
```

Create virtual environment and install dependancies:

```bash
uv sync
```

### Usage

Start worminator:

```bash
uv run main.py
```

## Configuration<a id="configuration"></a>

Create a `.env` file in project root following `.env.example`

## Contributing<a id="contributing"></a>

Contributions are very appreciated. Before starting work on a new feature, check on discord to make sure it's not already in the works by someone else.

## License<a id="license"></a>

Should probably add a license.
