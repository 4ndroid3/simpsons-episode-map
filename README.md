# 🍩 Los Simpson: Mapa de Episodios

Mapa personal de episodios de *Los Simpson*: un heatmap con todos los capítulos por temporada,
la puntuación de cada uno y las referencias del mejor momento de cada persona, más un mapa
con el **promedio** entre dos personas.

## Qué hace

- **Mapa por persona**: heatmap con temporadas en columnas y episodios en filas. Cada casilla
  se abre en un modal para puntuar (1–10) y escribir las referencias del mejor momento de esa
  persona.
- **Mapa de promedios**: elige a las dos personas y ves el promedio de sus puntuaciones por
  episodio. Al abrir un episodio aparecen las referencias de ambas personas.

## Requisitos

- Docker + Docker Compose (en el PC con el que vas a verlo).

## Levantar el proyecto

```bash
cd Proyectos/simpsons-episode-map
docker compose up -d --build
```

- Interfaz web: **http://localhost:8000**

## Desde otra PC o el celular (misma red WiFi)

1. Con el PC encendido y Docker levantado (`docker compose up -d`).
2. Obtén la IP local del PC (Windows: `ipconfig` → IPv4; Linux/Mac: `ifconfig` o `ip addr`).
3. En el celular o la otra PC, abre: `http://<IP-LAN-del-PC>:8000`

Ejemplo: `http://192.168.1.35:8000`

## Datos

- Persistencia en **SQLite** dentro del volumen de Docker `simpsons_data`.
- Temporadas 1–12 (269 episodios) precargadas.
- Cada episodio tiene título en español latino, título original y una sinopsis breve.
- La app migra automáticamente títulos y sinopsis al iniciar sin borrar personas,
  puntuaciones ni referencias existentes.

## Contenido y atribución

- Los títulos en español y las sinopsis se basan en el contenido de
  [Simpsons Wiki en español](https://simpsons.fandom.com/es/) y de
  [Wikipedia en español](https://es.wikipedia.org/wiki/Anexo:Episodios_de_Los_Simpson),
  disponibles bajo licencias **CC BY-SA**. Este proyecto es personal y sin fines de lucro.
- Las sinopsis de la primera temporada son notas propias pensadas como referencia rápida.
- *Los Simpson* y sus personajes son marcas de sus respectivos dueños.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/persons` | Lista personas |
| POST | `/api/persons` | Crear persona `{ "name": "..." }` |
| DELETE | `/api/persons/<id>` | Eliminar persona |
| GET | `/api/seasons` | Temporadas con número de episodios |
| GET | `/api/seasons/<n>/episodes` | Episodios de una temporada (con puntuaciones y referencias por persona) |
| GET | `/api/episodes/all?person=<id>` | Todos los episodios con la puntuación de una persona |
| POST | `/api/episodes` | Crear/editar episodio `{ "season": n, "number": n, "title": "...", "references": "..." }` |
| POST | `/api/references` | Referencia de una persona `{ "person_id": n, "season": n, "number": n, "references": "..." }` |
| POST | `/api/scores` | Puntuación `{ "person_id": n, "season": n, "episode_number": n, "value": n }` (1–10) |
| DELETE | `/api/scores?person_id=&season=&episode_number=` | Borrar puntuación |
| GET | `/api/averages?person_a=<id>&person_b=<id>` | Promedios de todos los episodios (con referencias de ambas personas) |

## Desarrollo local (sin Docker)

```bash
cd Proyectos/simpsons-episode-map
python3 -m venv venv
source venv/bin/activate  # o venv\Scripts\activate en Windows
pip install -r backend/requirements.txt
DB_PATH=/tmp/opencode/simpsons.db flask --app backend.app run --host 0.0.0.0 --port 8000
```
