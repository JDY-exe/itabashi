# Itabashi

Small Python service for a Raspberry Pi Zero 2 W that renders currently playing Last.fm lyrics to an 800x480 Pimoroni Inky/Spectra display.

## Configuration

Create a local `.env` file from the example:

```bash
cp .env.example .env
```

Required:

- `LASTFM_API_KEY`
- `LASTFM_USER`
- `GENIUS_ACCESS_TOKEN`

Optional:

- `POLL_SECONDS=20`
- `OUTPUT_MODE=inky|png`
- `PNG_OUTPUT=out/current.png`
- `CACHE_DIR=.cache/itabashi`

## Dry Run

```bash
OUTPUT_MODE=png itabashi-dry-run
```

The dry run writes `out/current.png` without requiring Pi display hardware.

## Service

```bash
itabashi
```
