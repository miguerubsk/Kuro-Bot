# requester-bot

Kuro, bot de Telegram para pedir animes: busca el nombre en japanpaw.com, saca el enlace
`paste.japan-paw.net/?v=…` de la página del anime y se lo manda a Anime-Automator
(`POST /download`).

- El chat `ADMIN_CHAT_ID` no tiene límites y sus peticiones se envían directamente.
- El resto de chats tienen `WEEKLY_LIMIT` peticiones cada 7 días (ventana móvil) y
  cada petición necesita que el admin la apruebe. Las rechazadas no cuentan para el cupo.
- Si el anime está en emisión, se avisa a quien lo pidió de que solo se bajan los
  capítulos publicados hasta ese momento.

## Puesta en marcha
1. Crea un bot **nuevo** con @BotFather (no reutilices el token de Anime-Automator:
   dos procesos haciendo polling con el mismo token se pisan).
2. `cp .env.example .env` y rellena: `TELEGRAM_BOT_TOKEN` y `ADMIN_CHAT_ID`.
   Para saber el id de un chat, escribe `/id` al bot (funciona aunque aún no tenga permisos).
3. Acceso del resto de chats:
   - `ALLOWED_CHAT_IDS=111,222` → solo esos chats.
   - Vacío + `ACCESS_KEYWORD=xxx` → cualquiera que mande `/start xxx` (se te avisa de cada alta).
   - Ambos vacíos → abierto a cualquiera (con aviso de que todo lo revisa el admin).
4. Anime-Automator tiene que estar levantado (este stack se une a su red `anime-automator_default`).
5. `docker compose up -d --build && docker compose logs -f`

## Comandos
- Todos: `/pedir <nombre>` (o escribir el nombre en privado), `/cupo`, `/id`, `/ayuda`.
- Admin: `/pendientes`, `/resetcupo [chat]`, `/descargados` (lo bajado por cada cliente).

Datos: `./data/requester.db` (SQLite; no se sube al repositorio).
Para reiniciar rápido, copia `restart.sh.example` a `restart.sh`.

## Código
- `bot/kuro.py`: crea y conecta todas las piezas; `bot/app.py`: arranque.
- `bot/handlers/`: comandos y botones (una clase por cada uno, con `@register`).
- `bot/orders/`: encargos (envío, biblioteca, aprobación).
- `bot/persona/`: la personalidad de Kuro; todas las frases están en `lines.py`.
- `bot/services/`: Anime-Automator, la web de búsqueda y AniList.
- `bot/events/`: avisos de progreso de Anime-Automator (`POST /events`).

## Pruebas
Usan dobles: no hablan con Telegram ni descargan nada.

    docker compose build
    docker run --rm -v "$PWD:/src" -w /src --entrypoint python requester-bot-requester-bot -m unittest
