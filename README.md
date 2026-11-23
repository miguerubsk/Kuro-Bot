# requester-bot

Kuro, bot de Telegram para pedir animes: busca el nombre en japanpaw.com, saca el enlace
`paste.japan-paw.net/?v=…` de la página del anime y se lo manda a Anime-Automator
(`POST /download`).

- El chat `ADMIN_CHAT_ID` no tiene límites y sus peticiones se envían directamente.
- El resto de chats tienen `WEEKLY_LIMIT` peticiones cada 7 días (ventana móvil) y
  cada petición necesita que el admin la apruebe. Las rechazadas no cuentan para el cupo.
- Si el anime está en emisión, se avisa a quien lo pidió de que solo se bajan los
  capítulos publicados hasta ese momento.

## Seguimiento semanal (change-detection.io y el Drive)
Si se pide algo en emisión (suelto o dentro de «todas las temporadas»), Kuro ofrece vigilarlo.
Al cliente se le crea el seguimiento cuando el admin lo aprueba; al admin, al momento. Si ese
anime ya se vigila (otro cliente o un watch hecho a mano), se apunta sin crear nada.
Cada cliente tiene `TRACKING_LIMIT` seguimientos.

Hay dos vigilantes, elegidos con `TRACKING_SOURCES`:
- `changedetection`: un watch de la página de pastes que mira solo la rejilla de capítulos
  (`.tab_content .ep-grid`) cada `TRACKING_CHECK_MINUTES`. Avisa a Anime-Automator (`/webhook`).
- `drive`: Kuro manda a Anime-Automator la lista completa (`PUT /watches`, con `CALLBACK_SECRET`):
  URL, título de la ficha (con él elige la carpeta) y ventana. Anime-Automator mira la carpeta
  del anime en la unidad de Drive de emisión cada 10 min, sin Chrome. La lista se manda cuando
  cambia algo, al arrancar y tras cada repaso; si falla, se reintenta cada 10 min.

Los dos acaban en el mismo encolado, que nunca baja dos veces lo mismo.

- **Ventana**: como mucho 24 h desde la hora de emisión de AniList (`TRACKING_WINDOW_HOURS`,
  24 por defecto y como máximo). Sin hora en AniList, el día del estreno entero *en Japón*
  (de su medianoche a la siguiente, pasado a la hora local: en invierno, de 16:00 a 16:00).
  Sin ningún dato, se mira siempre (change-detection cada 6 h).
- Cada 12 h se repasa: si la web ya no lo tiene en emisión, se termina y se avisa. Si cambia la
  hora de emisión, o el cambio de hora mueve la del estreno, se ajusta la ventana en los dos.
  Las ventanas antiguas de más de 24 h se recortan en el primer repaso tras arrancar.
  Los watches hechos a mano no se tocan.
- `/seguimientos`: lista y 🗑 para quitar (el admin ve todos).

### Del change-detection al Drive, poco a poco
1. **Los dos a la vez** (`TRACKING_SOURCES=changedetection,drive`, como está ahora).
   Durante unas semanas, compara quién detecta antes cada capítulo. En el log de
   Anime-Automator se ve si el encolado vino del Drive o del webhook, y `GET /watches`
   enseña el estado de cada anime en el Drive. Fíjate sobre todo en los animes sin `SxxEyy`
   (numeración absoluta), que en el Drive van más lentos.
2. **El Drive delante, change-detection de respaldo**: sube `TRACKING_CHECK_MINUTES`
   (p. ej. a 120 o 180). change-detection gasta menos Chrome y solo pilla lo que el Drive
   no vea. El repaso tras arrancar lo aplica también a los watches que ya existen.
3. **Solo el Drive** (`TRACKING_SOURCES=drive`): en el siguiente repaso (a los 5 min de
   arrancar), Kuro borra de change-detection los watches que creó él, te avisa y deja de
   crear más. Los hechos a mano siguen allí. El seguimiento funciona aunque no haya
   `CHANGEDETECTION_URL`.
4. **Marcha atrás**: con `TRACKING_SOURCES=changedetection`, Kuro vacía la lista del Drive.
   Los watches de change-detection se vuelven a crear al reactivar cada seguimiento (o
   añadiéndolos a mano); los activos no se recrean solos.

## Por torrent (lo que no está en la web)
Si la búsqueda no encuentra nada, Kuro enseña las opciones de AniList (series, no películas) y,
al elegir una, pregunta a Anime-Automator qué hay por torrent (`POST /torrent/check`, con
`CALLBACK_SECRET`): capítulos, temporada y carpeta. Al confirmar es un encargo normal (un carro,
visto bueno del admin, avisos de cada capítulo) que va a `POST /torrent/download`.

- Anime-Automator elige el release de cada capítulo: Erai-raws > subtítulos múltiples > WEB-DL > 1080p.
  Descarta doblajes y todo lo que no anuncie subtítulos en español (Erai-raws los trae aunque no
  lo diga); si aun así un archivo llega sin ellos, ese capítulo falla y se avisa.
- La temporada sale de las precuelas de AniList. El admin la cambia con las flechas antes de
  pedirlo (lo suyo) o en el mensaje de aprobación (lo de un cliente).
- `TORRENT_ACCESS`: `admin` (por defecto, solo tú), `all` (también los clientes) u `off`.
- A los clientes se les dice que va «por los tejados (torrent)» y que tarda más; nunca se nombra la web.
- Aún no: películas y lotes («01 ~ 11», lo único que hay de muchas series viejas).

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
- Todos: `/pedir <nombre>` (o escribir el nombre en privado), `/carros` (o `/cupo`), `/seguimientos`, `/id`, `/ayuda`.
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
- `bot/orders/torrent.py` y `bot/handlers/torrent.py`: encargos por torrent.
- `bot/events/`: avisos de progreso de Anime-Automator (`POST /events`).
- `bot/tracking/`: seguimiento semanal (change-detection) y su horario.

## Pruebas
Usan dobles: no hablan con Telegram ni descargan nada.

    docker compose build
    docker run --rm -v "$PWD:/src" -w /src --entrypoint python requester-bot-requester-bot -m unittest
