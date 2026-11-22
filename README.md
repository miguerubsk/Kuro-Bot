# requester-bot

Kuro, bot de Telegram para pedir animes: busca el nombre en japanpaw.com, saca el enlace
`paste.japan-paw.net/?v=…` de la página del anime y se lo manda a Anime-Automator
(`POST /download`).

- El chat `ADMIN_CHAT_ID` no tiene límites y sus peticiones se envían directamente.
- El resto de chats tienen `WEEKLY_LIMIT` peticiones cada 7 días (ventana móvil) y
  cada petición necesita que el admin la apruebe. Las rechazadas no cuentan para el cupo.
- Si el anime está en emisión, se avisa a quien lo pidió de que solo se bajan los
  capítulos publicados hasta ese momento.

## Seguimiento semanal (change-detection.io)
Si se pide algo en emisión (suelto o dentro de «todas las temporadas»), Kuro ofrece vigilarlo.
Al cliente se le crea el seguimiento cuando el admin lo aprueba; al admin, al momento. Si ese
anime ya se vigila (otro cliente o un watch hecho a mano), se apunta sin crear nada.
Cada cliente tiene `TRACKING_LIMIT` seguimientos.

- Se vigila la página de pastes y solo la rejilla de capítulos (`.tab_content .ep-grid`).
  change-detection avisa a Anime-Automator (`/webhook`) y este baja lo que falte.
- Solo se comprueba desde la hora de emisión (AniList) durante `TRACKING_WINDOW_HOURS`,
  cada `TRACKING_CHECK_MINUTES`. Sin horario en AniList, se usa el día del estreno.
- Cada 12 h se repasa: si la web ya no lo tiene en emisión, se borra el watch y se avisa.
  Si cambia la hora de emisión, se ajusta la ventana. Los watches hechos a mano no se tocan.
- `/seguimientos`: lista y 🗑 para quitar (el admin ve todos).

## Bloqueos
Si la web da un certificado falso (bloqueo de LaLiga), se busca otra IP de Cloudflare por DoH.
Si nos niega el acceso (403) y no hay IP libre, se usa `BLOCK_BYPASS_PROXY` (p. ej. Tor)
durante 6 h para ese servidor, igual que hace Anime-Automator.

## Puesta en marcha
1. Crea un bot **nuevo** con @BotFather (no reutilices el token de Anime-Automator:
   dos procesos haciendo polling con el mismo token se pisan).
2. `cp .env.example .env` y rellena: `TELEGRAM_BOT_TOKEN` y `ADMIN_CHAT_ID`.
   Para saber el id de un chat, escribe `/id` al bot (funciona aunque aún no tenga permisos).
3. Acceso del resto de chats:
   - `ALLOWED_CHAT_IDS=111,222` → solo esos chats.
   - Vacío + `ACCESS_KEYWORD=xxx` → cualquiera que mande `/start xxx` (se te avisa de cada alta).
   En los dos casos, a quien no conoce Kuro le da su código de cliente, y tú puedes
   dejarle pasar con `/alta código [nombre]` (con contraseña, también le dice que la use).
   - Ambos vacíos → abierto a cualquiera (con aviso de que todo lo revisa el admin).
4. Anime-Automator tiene que estar levantado (este stack se une a su red `anime-automator_default`).
5. `docker compose up -d --build && docker compose logs -f`

## Comandos
- Todos: `/pedir <nombre>` (o escribir el nombre en privado), `/cupo`, `/seguimientos`, `/id`, `/ayuda`.
- Admin: `/pendientes`, `/resetcupo [chat]`, `/descargados` (lo bajado por cada cliente),
  `/alta código [nombre]` (dejar pasar a alguien por su código).

Datos: `./data/requester.db` (SQLite; no se sube al repositorio).
Para reiniciar rápido, copia `restart.sh.example` a `restart.sh`.

## Código
- `bot/kuro.py`: crea y conecta todas las piezas; `bot/app.py`: arranque.
- `bot/handlers/`: comandos y botones (una clase por cada uno, con `@register`).
- `bot/orders/`: encargos (envío, biblioteca, aprobación).
- `bot/persona/`: la personalidad de Kuro; todas las frases están en `lines.py` y la ficha de
  personajes (Kuro y el cazador, el canon de su historia) en `ficha.md`. De vez en
  cuando cuenta algo de su vida: a los clientes, más cuantos más animes se les han bajado
  (`TRUST_STEPS`); contigo, batallitas con animes que se bajaron de verdad.
- `bot/services/`: Anime-Automator, la web de búsqueda y AniList.
- `bot/events/`: avisos de progreso de Anime-Automator (`POST /events`).
- `bot/tracking/`: seguimiento semanal (change-detection) y su horario.

## Pruebas
Usan dobles: no hablan con Telegram ni descargan nada.

    docker compose build
    docker run --rm -v "$PWD:/src" -w /src --entrypoint python requester-bot-requester-bot -m unittest
