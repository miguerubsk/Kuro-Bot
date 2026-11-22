"""
Frases de Kuro (solo datos; la lógica está en persona/__init__.py).

Ficha del personaje (para que todas las frases suenen a la misma persona):

- Gato negro, ex-camarada felyne. Pasó años acompañando a cazadores
  (barriles bomba, carne asada, monstruos enormes…) y se retiró. Ahora
  trapichea con anime en los bajos fondos de internet.
- Habla con «nya» y juegos de palabras gatunos al estilo felyne
  («miauestro», «miaugnífico», «en un santiamiau», «gatástrofe»…). A veces
  habla de sí mismo en tercera persona («Kuro no falla»).
- Carácter: pícaro y fanfarrón pero honrado. Su «palabra de felyne» va a
  misa: lo que no consigue no lo cobra. Leal hasta los bigotes a su «miauestro»
  (el admin, como el cazador al que acompaña un felyne en Monster Hunter),
  y con los clientes es zalamero, como un comerciante de callejón.
  Al admin le llama «miauestro», y ante los clientes habla de él como
  «el miauestro». A los clientes, «cliente», «forastero», «amigo»…
- Le pierden el atún y el pescado; duerme en una caja de cartón; odia el
  agua, a los perros y las redadas («la perrera»). Bufa («Fsss…») cuando
  algo no le gusta y se ríe con «fufufu».
- Es nocturno: de noche está más despierto y lo comenta.

Todos los textos que ve la gente salen de aquí. Cada clave tiene varias
variantes y se elige una al azar (sin repetir la misma dos veces seguidas).
Las plantillas son HTML de Telegram:

- {voc} / {Voc}: cómo llama a quien lee (al admin «miauestro», a los
  demás «cliente»…), en minúscula / con mayúscula inicial.
- {site}: un nombre al azar para la web donde se busca.
- Los valores que se pasan a say() se escapan solos, salvo los que acaban en
  "_html" (ya vienen formateados).

Extras:
- NIGHT_LINES: variantes que se suman a las normales de madrugada.
- ASIDES: de vez en cuando, en las claves de ASIDE_KEYS, Kuro añade un gesto
  gatuno al final («<i>se lame una pata</i>»).
"""

# Cómo llama Kuro al admin y al resto
BOSS_TITLES = ["miauestro", "miauestro", "miauestro", "miauestro-nya"]
CLIENT_TITLES = ["cliente", "cliente", "forastero", "amigo", "cliente-nya"]

SITE_NAMES = [
    "la dip güeb",
    "los bajos fondos de internet",
    "el mercado negro del anime",
    "las catacumbas de la red",
    "el callejón de los fansubs",
    "la trastienda del internet",
    "el tejado de los gatos piratas",
    "el contenedor de detrás del sushi",
    "la lonja clandestina",
    "el sótano de los otakus perdidos",
    "las alcantarillas de la red",
    "el bazar de medianoche",
]

LINES: dict[str, list[str]] = {
    # ------------------------------------------------------------ ayuda
    "help_intro_boss": [
        "🐈‍⬛ ¡{Voc}! Kuro reportándose para el servicio, nya. Tú dime un nombre "
        "(o <code>/pedir nombre</code>) y me escurro por {site} a por él.",
        "🐈‍⬛ Kuro, a sus órdenes, {voc}. Bigotes afilados y zarpas listas: "
        "escríbeme un anime (o <code>/pedir nombre</code>) y lo traigo en un santiamiau.",
        "🐈‍⬛ ¡{Voc}, ha vuelto! Kuro tenía la caja de cartón calentita esperándote, nya. "
        "Dime un anime (o <code>/pedir nombre</code>) y salgo por {site}.",
        "🐈‍⬛ Como en los viejos tiempos de cacería, {voc}: tú señalas la presa y Kuro la trae. "
        "Escribe un nombre (o <code>/pedir nombre</code>).",
    ],
    "help_intro_client": [
        "🐈‍⬛ Bienvenido, {voc}. Soy <b>Kuro</b>, gato de confianza con contactos en {site}, nya.\n"
        "Dime el nombre de un anime (o <code>/pedir nombre</code>) y veré qué puedo pescar.",
        "🐈‍⬛ Nyaa~ ¿Un encargo, {voc}? Soy <b>Kuro</b> y conozco cada rincón de {site}.\n"
        "Escríbeme el nombre (o <code>/pedir nombre</code>) y me pongo a husmear.",
        "🐈‍⬛ Pasa, pasa, {voc}, que entra el frío. Aquí <b>Kuro</b>, ex-camarada de cazadores "
        "y ahora proveedor de anime de {site}.\n"
        "Dime qué buscas (o <code>/pedir nombre</code>) y lo olfateo.",
        "🐈‍⬛ Fufufu… Otro cliente con buen gusto. Soy <b>Kuro</b>, {voc}, y si algo se mueve "
        "por {site}, yo lo sé.\nEscríbeme un nombre (o <code>/pedir nombre</code>).",
    ],
    "help_admin": [
        "Contigo no hay cuentas, {voc}: sin límites y sin esperar a nadie, nya.",
        "Para ti la casa es libre, {voc}. Pide lo que quieras, que yo no llevo la cuenta, nya.",
        "Tú eres quien pone el atún en mi cuenco, {voc}: sin cupo y sin preguntas.",
    ],
    "help_user": [
        "Normas de la casa, {voc}: <b>{limit} encargos por semana</b>, y el miauestro revisa cada uno "
        "antes de que salga. Lo que no se consigue no se cobra, palabra de felyne.",
        "Te lo digo clarito, {voc}: <b>{limit} encargos a la semana</b>, todos con el visto bueno del "
        "miauestro. Si un encargo sale mal, no te lo cobro, nya.",
        "El trato es sencillo, {voc}: <b>{limit} encargos por semana</b>, el miauestro da el visto bueno "
        "y Kuro hace el resto. Si algo falla, no gasta cupo. Palabra de felyne.",
    ],
    "open_warning": [
        "⚠️ Ojo, {voc}: este es un negocio privado. Cada encargo lo mira el miauestro con lupa y puede "
        "decir que no, nya.",
        "⚠️ Que quede claro, {voc}: aquí manda el miauestro. Cada encargo pasa por sus manos y puede "
        "rechazarlo, nya.",
    ],
    "welcome_new": [
        "🔓 ¡Contraseña correcta, nya! Pasa, {voc}, y cierra la gatera al entrar.",
        "🔓 Vienes de parte de alguien, ya veo. Bienvenido al tejado, {voc}~",
        "🔓 Fufufu, sabes la contraseña. Kuro te apunta en su libreta de garra, {voc}. ¡Adentro!",
        "🔓 Contraseña buena. Huele a cliente de fiar… y un poco a atún. Pasa, {voc}, nya.",
    ],
    # ---------------------------------------------------------- acceso
    "deny_id": [
        "🔒 Fsss… No te conozco. Si conoces al miauestro, pásale esto: <code>{chat_id}</code>",
        "🔒 Aquí solo se entra con invitación, nya. Tu número de socio sería <code>{chat_id}</code>; "
        "díselo al miauestro.",
        "🔒 Alto ahí, desconocido. Kuro no abre la gatera a cualquiera. Si el miauestro te conoce, "
        "dale este número: <code>{chat_id}</code>",
    ],
    "deny_keyword": [
        "🔒 Fsss… No te conozco. Si te han invitado, ya sabes: <code>/start contraseña</code>.",
        "🔒 Club privado, nya. Si tienes la contraseña: <code>/start contraseña</code>.",
        "🔒 Sin contraseña no hay trato. Si alguien te la ha dado: <code>/start contraseña</code>.",
    ],
    "chat_id": [
        "🐾 El número de este chat es <code>{chat_id}</code>, {voc}.",
        "🐾 Apuntado en mi libreta: este chat es el <code>{chat_id}</code>, {voc}.",
    ],
    "not_admin": [
        "😼 Buen intento, {voc}, pero eso solo lo toca el miauestro. Nya-nya.",
        "😼 Ni con siete vidas, {voc}. Eso es cosa del miauestro.",
        "😼 Fsss… Esa zarpa quieta, {voc}. Eso es del miauestro.",
        "😼 Kuro es leal, {voc}, y eso solo lo hace el miauestro. Ni por todo el atún del mundo.",
    ],
    # Se muestra como alerta: texto plano, sin HTML
    "not_authorized": [
        "Fsss… no puedes tocar eso.",
        "Zarpas fuera, nya. Eso no es tuyo.",
        "Fsss… eso no es para ti.",
    ],
    # -------------------------------------------------------- búsqueda
    "ask_name": [
        "¿Y qué busco, {voc}, bolas de pelo? Dime un nombre, p. ej. <code>/pedir Frieren</code>",
        "Necesito un nombre para olfatear, {voc}, nya. Algo como <code>/pedir Frieren</code>",
        "Kuro tiene buen olfato, {voc}, pero no lee mentes. Dime algo como <code>/pedir Frieren</code>",
    ],
    "searching": [
        "🔎 Me escurro por {site} a buscar «{query}»… nya.",
        "🔎 Preguntando a los gatos callejeros de {site} por «{query}»…",
        "🔎 Olfateando {site} en busca de «{query}». Bigotes en alerta…",
        "🔎 Garras a la obra: rastreando «{query}» por {site}…",
        "🔎 Me pongo la gabardina y bajo a {site} a preguntar por «{query}»…",
        "🔎 Sigilo de felyne activado. Buscando «{query}» en {site}…",
        "🔎 «{query}»… Conozco a un gato en {site} que me debe un favor. Voy a verle.",
        "🔎 Agazapado en {site}, esperando a que asome «{query}»…",
    ],
    "search_error": [
        "⚠️ ¡Gatástrofe! {site} no me abre la gatera ahora mismo. Vuelve en un rato, {voc}.",
        "⚠️ Hay redada en {site}, {voc}, y no puedo entrar. Prueba más tarde, nya.",
        "⚠️ La perrera ronda {site} y Kuro no se arriesga, {voc}. Inténtalo dentro de un rato.",
        "⚠️ Fsss… {site} está cerrado a cal y canto. Vuelve luego, {voc}, nya.",
    ],
    "not_found": [
        "😿 Ni rastro de «{query}» en {site}, {voc}. Prueba con el título en romaji "
        "(p. ej. <i>Sousou no Frieren</i>) o con menos palabras.",
        "😿 Mis contactos de {site} no saben nada de «{query}», nya. A veces lo conocen por el "
        "nombre en romaji (<i>Sousou no Frieren</i>) o con menos palabras.",
        "😿 He husmeado {site} de arriba abajo y de «{query}» nada, {voc}. ¿Probamos con el "
        "nombre en romaji (<i>Sousou no Frieren</i>) o algo más corto?",
        "😿 «{query}»… Ese pescado no nada por {site}, {voc}. Prueba con el título japonés en "
        "letras latinas (<i>Sousou no Frieren</i>) o con menos palabras.",
    ],
    "alias_hint": [
        "🐾 Por {site} a «{query}» no lo conocen así, pero mis contactos dicen que es <b>{alias}</b>, nya.",
        "🐾 «{query}», ¿eh? Por estos tejados lo llaman <b>{alias}</b>. ¡Miauravilloso, {voc}!",
        "🐾 Ah, te refieres a <b>{alias}</b>. En {site} lo tienen con ese nombre, nya.",
        "🐾 Psst, {voc}: en {site} «{query}» va de incógnito como <b>{alias}</b>. Pero a Kuro no se le escapa.",
    ],
    "pick": [
        "Esto es lo que circula por {site}, {voc}. ¿Cuál te llevas?",
        "Mira lo que he pescado, {voc}~ ¿Cuál es el bueno?",
        "Fufufu, tengo género. ¿Cuál quieres, {voc}?",
        "Abro la gabardina y… ¡tachán! Elige, {voc}, nya.",
        "Todo fresco, recién sacado de {site}. ¿Cuál te pongo, {voc}?",
    ],
    # /descargados (solo el admin)
    "history_mine": [
        "📜 Tu cuaderno de caza, {voc}: <b>{count}</b> presa(s) traídas a la madriguera.",
        "📜 Lo que me has encargado tú, {voc}: <b>{count}</b>. Buen ojo, nya.",
        "📜 Repaso de tu botín, {voc}: <b>{count}</b>. Kuro lo apunta todo, hasta lo que pides a deshoras.",
        "📜 El inventario del miauestro: <b>{count}</b>. Ordenadito, como mis bigotes.",
    ],
    "history_empty_mine": [
        "📜 Tu lista está vacía, {voc}. ¿Me tienes a dieta?",
        "📜 Ni un encargo tuyo apuntado, {voc}. El cuaderno huele a nuevo, nya.",
    ],
    "history_client_one": [
        "📜 {who} solo se ha llevado uno. Cliente de paso, como los gatos callejeros.",
        "📜 {who}: un encargo y gracias. Le tengo fichado, por si vuelve, nya.",
        "📜 Una sola pieza para {who}. Prueba la mercancía antes de hacerse fijo, fufufu.",
    ],
    "history_client_few": [
        "📜 {who}: <b>{count}</b> encargos. Va cogiendo confianza, nya.",
        "📜 {who} ya se ha llevado <b>{count}</b>. Le empiezo a reconocer por las pisadas.",
        "📜 <b>{count}</b> para {who}. Si sigue así, le guardo un cojín en el mostrador.",
    ],
    "history_client_many": [
        "📜 {who} es cliente de la casa: <b>{count}</b> encargos. Ya le guardo sitio en el tejado.",
        "📜 <b>{count}</b> encargos de {who}. Cliente VIP: Vale Infinitas Pescaditos, nya.",
        "📜 {who} lleva <b>{count}</b>. A este paso le pongo su nombre a una caja de cartón.",
    ],
    "history_client_waiting": [
        "📜 {who} todavía no ha estrenado nada: lo suyo aún viene de camino.",
        "📜 A {who} aún no le ha llegado nada, nya. Lo suyo está en el saco.",
    ],
    "history_empty_client": [
        "📜 {who} aún no se ha llevado nada. Mira mucho y compra poco, nya.",
        "📜 Nada a nombre de {who} todavía. Olfatea el escaparate y se va.",
    ],
    "history_in_progress": [
        "⏳ <b>En camino</b> (aún bajando, nya):",
        "⏳ <b>En el saco</b>, todavía llegando:",
    ],
    "pick_cards": [
        "Esto es lo que circula por {site}, {voc}. Te enseño las fichas una a una: pasa con ◀️ ▶️ y dime cuál te llevas.",
        "Mira lo que he pescado, {voc}~ Cada uno con su portada y su historia. ◀️ ▶️ para hojear.",
        "Fufufu, abro la gabardina y te enseño el género ficha a ficha, {voc}. Pasa con ◀️ ▶️, nya.",
        "Todo fresco, recién sacado de {site}. Hojea con ◀️ ▶️ y elige, {voc}.",
        "Kuro te pone el catálogo delante, {voc}: portada, de qué va y cuántos capítulos. ◀️ ▶️ para pasar.",
    ],
    "cancelled": [
        "Como quieras, {voc}. Me vuelvo a mi caja de cartón. 🐈‍⬛",
        "Trato cancelado. Sin rencores, nya.",
        "Vale, {voc}. Kuro guarda la mercancía y se echa una siesta. 🐈‍⬛",
        "Otra vez será, {voc}. La gatera queda abierta, nya.",
    ],
    "expired": [
        "⚠️ Esa lista se ha quedado más vieja que el pienso de ayer, {voc}. Pídemelo otra vez.",
        "⚠️ Esa mercancía ya no está en el escaparate, {voc}. Vuelve a buscarlo, nya.",
    ],
    "reading_post": [
        "⏳ Echando un ojo a la mercancía: <b>{title}</b>…",
        "⏳ Inspeccionando <b>{title}</b> con lupa de detective, nya…",
        "⏳ Olisqueando <b>{title}</b> para ver si está fresco…",
        "⏳ Un momento, {voc}, que reviso <b>{title}</b> pata por pata…",
    ],
    "post_error": [
        "⚠️ No he podido abrir la ficha de ese anime, {voc}. Prueba en un rato, nya.",
        "⚠️ La ficha de ese anime se me ha atascado en las zarpas, {voc}. Inténtalo luego.",
    ],
    "no_link": [
        "😿 He encontrado <b>{title}</b>, pero no hay enlace de descarga, {voc}. Ni un gato puede "
        "sacar algo de donde no hay.",
        "😿 <b>{title}</b> está en el escaparate, pero no hay forma de llevárselo, {voc}. "
        "Ni con siete vidas, nya.",
    ],
    # --------------------------------------- comprobación de la biblioteca
    "checking_library": [
        "📚 Un momento, {voc}: miro si <b>{title}</b> ya está en el almacén…",
        "📚 Repasando las estanterías del almacén por si ya tenemos <b>{title}</b>…",
        "📚 Antes de salir de caza, Kuro mira la despensa: ¿tenemos ya <b>{title}</b>?",
    ],
    "library_complete": [
        "😸 ¡Buenas noticias, {voc}! <b>{title}</b> ya está entero en el almacén ({have} capítulos). "
        "No hace falta encargo y tu cupo sigue intacto, nya.",
        "😸 Fufufu, <b>{title}</b> ya duerme en nuestras estanterías, {voc}: {have} capítulos, "
        "todos en su sitio. Esto no gasta cupo.",
        "😸 No hace falta salir de caza, {voc}: <b>{title}</b> ya está completito en el almacén "
        "({have} capítulos). Tu cupo, intacto.",
    ],
    "library_movie": [
        "😸 La película <b>{title}</b> ya está en el almacén, {voc}. No hace falta encargo y tu "
        "cupo sigue intacto, nya.",
        "😸 <b>{title}</b> ya está en la estantería de pelis, {voc}. Esto no gasta cupo.",
    ],
    "library_busy": [
        "😸 Lo que falta de <b>{title}</b> ya viene de camino por otro encargo, {voc}. "
        "No hace falta pedirlo otra vez, y tu cupo sigue intacto.",
        "😸 Otro gato ya va a por <b>{title}</b>, {voc}. Llegará solo; esto no gasta cupo, nya.",
    ],
    # se añade a "sent_to_admin" cuando ya hay parte en la biblioteca
    "library_partial": [
        "\n📚 Ya tenemos {have} de {available} capítulos: el encargo es solo por los {count} "
        "que faltan ({ranges}).",
        "\n📚 En el almacén ya hay {have} de {available}; Kuro solo traería los {count} que faltan "
        "({ranges}).",
    ],
    # se añade a "sent_to_admin" cuando lo que falta ya está, pero en peor calidad
    "library_upgrade": [
        "\n📀 Ya lo tenemos, pero en peor calidad: Kuro lo cambia por el bueno y esto <b>no gasta cupo</b>.",
        "\n📀 En el almacén está en una versión pochita; la cambio por la buena sin cobrarte cupo, nya.",
    ],
    # ------------------------------------------------- todas las temporadas
    "pick_seasons": [
        "\n📦 Hay varias temporadas: puedes llevártelas todas por <b>un solo encargo</b>.",
        "\n📦 Oferta de la casa: todas las temporadas juntas cuentan como <b>un encargo</b>, nya.",
    ],
    "bundle_reading": [
        "⏳ Reuniendo todas las temporadas de <b>{title}</b> y mirando qué hay ya en el almacén…",
        "⏳ Kuro va estantería por estantería con las temporadas de <b>{title}</b>…",
    ],
    "bundle_all_have": [
        "😸 Todas las temporadas de <b>{title}</b> ya están en el almacén, {voc}. No hace falta encargo "
        "y tu cupo sigue intacto.",
        "😸 Nada que cazar: <b>{title}</b> ya está entero, todas sus temporadas. Tu cupo, intacto, nya.",
    ],
    "bundle_sent": [
        "📨 ¡Lote apuntado, {voc}! <b>{title}</b>: {items_html}\nCuenta como <b>un solo encargo</b>. "
        "Se lo paso al miauestro y te aviso, nya.\nTe quedan {left} de {limit} esta semana.",
        "📨 Todo al saco: <b>{title}</b> ({items_html}). Un encargo nada más, palabra de felyne. "
        "Ahora decide el miauestro.\nTe quedan {left} de {limit} esta semana.",
    ],
    "bundle_skipped": [
        "\n😸 Ya en el almacén (no se piden): {items_html}.",
        "\n😸 Estas ya las tenemos y no entran en el lote: {items_html}.",
    ],
    "bundle_rejected": [
        "❌ El miauestro ha dicho que no al lote de <b>{title}</b>, {voc}. No gasta cupo, nya.",
        "❌ Lote de <b>{title}</b> denegado. Tranquilo, {voc}, tu cupo sigue intacto.",
    ],
    "admin_bundle_request": [
        "📨 {Voc}, <b>{who}</b> quiere <b>todas las temporadas</b> (lote #{bundle}, cuenta como un encargo):",
        "📨 Encargo gordo, {voc}: <b>{who}</b> se lleva el lote completo (#{bundle}, un solo cupo):",
    ],
    "already_pending": [
        "⏳ Ya tienes un encargo de <b>{title}</b> en marcha, {voc}. Paciencia, que no soy mago… "
        "solo un gato, nya.",
        "⏳ <b>{title}</b> ya está en mi libreta, {voc}. Kuro no olvida un encargo, palabra de felyne.",
    ],
    # ------------------------------------------------------------- cupo
    "no_quota": [
        "⛔ Ya te has llevado tus {limit} encargos de esta semana, {voc}.{when_html}",
        "⛔ Se acabó el crédito, {voc}: {limit} encargos por semana y ya los tienes. Nya.{when_html}",
        "⛔ La libreta está llena, {voc}: ya van {limit} encargos esta semana.{when_html}",
        "⛔ Ni un encargo más, {voc}, que el miauestro me deja sin atún. Ya llevas {limit} esta semana.{when_html}",
    ],
    "no_quota_when": [
        " Vuelve el {date}.",
        " Tendrás hueco el {date}, nya.",
        " Te espero el {date} en el tejado.",
    ],
    "quota_left": [
        "Te quedan <b>{left}</b> de {limit} encargos esta semana, {voc}.",
        "Cuenta de la semana, {voc}: <b>{left}</b> de {limit} encargos disponibles, nya.",
        "Según mi libreta de garra, {voc}, te quedan <b>{left}</b> de {limit} esta semana.",
    ],
    "quota_admin": [
        "♾️ ¿Límite? ¿Para ti, {voc}? Nyaaa, ni hablar.",
        "♾️ Tú no tienes límite, {voc}. Pide sin miedo.",
        "♾️ ¿Contarte los encargos a ti, {voc}? Kuro no está tan loco, nya.",
    ],
    # ---------------------------------------------------------- petición
    "sent_to_admin": [
        "📨 Encargo de <b>{title}</b>{label} apuntado, {voc}. Se lo paso al miauestro y te aviso cuando "
        "diga algo, nya.\nTe quedan {left} de {limit} esta semana.",
        "📨 ¡Apuntado en mi libreta de garra! <b>{title}</b>{label}. Ahora decide el miauestro; "
        "ya te contaré, {voc}.\nTe quedan {left} de {limit} esta semana.",
        "📨 <b>{title}</b>{label}: encargo en el buzón del miauestro, {voc}. En cuanto mueva un bigote, "
        "te aviso.\nTe quedan {left} de {limit} esta semana.",
    ],
    "admin_unreachable": [
        "⚠️ No consigo localizar al miauestro, {voc}. Prueba más tarde (no te lo cuento como encargo).",
        "⚠️ El miauestro no contesta, {voc}. Vuelve luego, que esto no te gasta cupo, nya.",
    ],
    "sending": [
        "📤 Llevando el encargo de <b>{title}</b>{label} al almacén… nya.",
        "📤 Allá va <b>{title}</b>{label}, directo al almacén. En un santiamiau…",
        "📤 <b>{title}</b>{label} bien sujeto entre los dientes, camino del almacén…",
    ],
    "approved": [
        "👍 ¡El miauestro ha dado el visto bueno a <b>{title}</b>, {voc}! Miaugnífico.",
        "👍 ¡Trato hecho, nya! <b>{title}</b> va para dentro.",
        "👍 ¡Miauravilloso, {voc}! El miauestro dice que sí a <b>{title}</b>.",
        "👍 ¡Luz verde para <b>{title}</b>, {voc}! Kuro sale de caza.",
    ],
    "approved_boss": [
        "👍 ¡A la orden, {voc}! <b>{title}</b> va para dentro.",
        "👍 ¡Marchando <b>{title}</b>, {voc}! Nya.",
        "👍 Dicho y hecho, {voc}: <b>{title}</b> en camino.",
    ],
    "queued": [
        "📦 Hay {count} capítulo(s) en camino ({ranges}). Te aviso de cada uno según llegue, nya.",
        "📦 {count} capítulo(s) en la cola ({ranges}). Te los voy contando uno a uno, {voc}.",
        "📦 {count} capítulo(s) en el saco ({ranges}). Kuro te avisa de cada pieza que cobre.",
    ],
    "queued_untracked": ["📦 {count} capítulo(s) en camino ({ranges})."],
    "movie_queued": [
        "🎬 La película ya está en camino, {voc}. Te aviso en cuanto esté en su sitio, nya.",
        "🎬 Película en la cola. Prepárate las palomitas, {voc}… y algo de atún para mí.",
        "🎬 La peli va de camino, {voc}. Ve buscando sitio en el sofá, que Kuro se pide el cojín.",
    ],
    "rejected": [
        "❌ El miauestro ha dicho que no a <b>{title}</b>, {voc}. No te lo cuento como encargo, nya.",
        "❌ <b>{title}</b>: denegado por el miauestro. Tranquilo, {voc}, no gasta cupo.",
        "❌ Mala suerte, {voc}: el miauestro no quiere <b>{title}</b>. Tu cupo sigue intacto, nya.",
    ],
    "nothing_new": [
        "😸 <b>{title}</b> ya está entero en la colección, {voc}. No te lo cobro, nya.",
        "😸 ¡Ya lo tenemos todo! <b>{title}</b> está completito. Encargo gratis, {voc}.",
        "😸 <b>{title}</b> ya duerme en el almacén, {voc}, de la cabeza a la cola. Esto no se cobra.",
    ],
    "already_downloading": [
        "😸 <b>{title}</b> ya se está descargando por otro lado, {voc}. No te lo cobro.",
        "😸 Otro gato ya va a por <b>{title}</b>, {voc}. Para ti, gratis, nya.",
    ],
    "tech_failure": [
        "⚠️ ¡Gatástrofe técnica con <b>{title}</b>! Habrá que echarle un ojo; de momento no gasta cupo, {voc}.",
        "⚠️ Se me ha enredado el ovillo con <b>{title}</b>, {voc}. Toca revisarlo; no te cuenta como encargo.",
    ],
    "airing": [
        "📺 Está <b>en emisión</b>{progress}: te traigo lo que ya ha salido, pero los capítulos "
        "nuevos <b>no</b> llegarán solos, {voc}.",
        "📺 Ojo, que está <b>en emisión</b>{progress}: Kuro trae lo que hay, pero lo que salga "
        "después <b>no</b> llega solo, {voc}.",
    ],
    # ------------------------------------------------ progreso por capítulo
    "ep_done": [
        "✅ <b>{name}</b> — capítulo {ep:02d} entregado ({n}/{total}). Nya~",
        "🐾 Capítulo {ep:02d} de <b>{name}</b> listo ({n}/{total}).",
        "✅ ¡Pesca del día! El {ep:02d} de <b>{name}</b> ya está ({n}/{total}).",
        "🐟 Otro más para la cesta: <b>{name}</b> {ep:02d} ({n}/{total}).",
        "✅ <b>{name}</b> {ep:02d}, cazado y en su sitio ({n}/{total}).",
        "🐾 Ronroneo de satisfacción: <b>{name}</b> {ep:02d} entregado ({n}/{total}).",
    ],
    "ep_retry": [
        "⏳ El capítulo {ep:02d} de <b>{name}</b> se me resiste, {voc}. Lo vuelvo a intentar en {delay}.",
        "⏳ Bufff, el {ep:02d} de <b>{name}</b> no se deja cazar. Reintento en {delay}, nya.",
        "⏳ El {ep:02d} de <b>{name}</b> se ha escondido debajo del sofá. Vuelvo a por él en {delay}.",
    ],
    "ep_fallback": [
        "🔄 El capítulo {ep:02d} de <b>{name}</b> lo traigo por los tejados (torrent). Tardará algo más.",
        "🔄 La puerta principal está cerrada para el {ep:02d} de <b>{name}</b>: voy por los tejados "
        "(torrent). Tardará algo más, nya.",
    ],
    "ep_failed": [
        "😿 El capítulo {ep:02d} de <b>{name}</b> no ha podido ser, {voc}. Nya…",
        "😿 Se me ha escapado el {ep:02d} de <b>{name}</b>. Lo siento, {voc}.",
        "😿 El {ep:02d} de <b>{name}</b> se ha escurrido entre las zarpas, {voc}. Kuro lo siente.",
    ],
    "job_done_all": [
        "🎉 ¡<b>{name}</b> completo, {voc}! {done} capítulo(s) entregados. ¡Miaugnífico!",
        "🎉 Entrega terminada: <b>{name}</b>, {done} capítulo(s). Que lo disfrutes, {voc}~ nya.",
        "🎉 ¡Cacería completada! <b>{name}</b>: {done} capítulo(s), ni uno se ha escapado. "
        "Esto se celebra con atún, {voc}.",
        "🎉 <b>{name}</b> entero en el almacén, {voc}: {done} capítulo(s). Kuro no falla, nya.",
    ],
    "job_done_partial": [
        "🏁 <b>{name}</b> terminado, {voc}: {done} capítulo(s) entregados y {failed} que no han "
        "podido ser ({failed_ranges}).",
        "🏁 Cacería de <b>{name}</b> acabada, {voc}: {done} capítulo(s) en el saco y {failed} "
        "que se han escapado ({failed_ranges}). Nya…",
    ],
    "job_failed": [
        "😿 No he conseguido ni un capítulo de <b>{name}</b>, {voc}. Este encargo no te cuenta "
        "para el cupo, nya.",
        "😿 Vuelvo con las zarpas vacías: ni un capítulo de <b>{name}</b>, {voc}. No te lo cobro, "
        "palabra de felyne.",
    ],
    "movie_done": [
        "🎬 ¡<b>{name}</b> ya está en su sitio, {voc}! A disfrutar, nya~",
        "🎬 Película entregada: <b>{name}</b>. ¡Miauravilloso! Palomitas para ti, atún para mí.",
        "🎬 <b>{name}</b> en el almacén, {voc}. Apaga la luz, que empieza la función, nya.",
    ],
    "movie_retry": [
        "⏳ La película <b>{name}</b> se resiste, {voc}. Lo vuelvo a intentar en {delay}.",
        "⏳ <b>{name}</b> se hace de rogar, {voc}. Kuro vuelve a la carga en {delay}, nya.",
    ],
    "movie_failed": [
        "😿 No he podido traer <b>{name}</b>, {voc}. No te cuenta para el cupo, nya.",
        "😿 <b>{name}</b> se me ha escapado, {voc}. No te la cobro, palabra de felyne.",
    ],
    "movie_already": [
        "😸 La película <b>{title}</b> ya está en la colección, {voc}. No te lo cobro.",
        "😸 <b>{title}</b> ya está en la estantería, {voc}. Gratis, nya.",
    ],
    # --------------------------------------------------- mensajes al admin
    "admin_request": [
        "📨 ¡{Voc}, nya! <b>{who}</b> quiere un encargo (#{req_id}):",
        "📨 Cliente en la puerta, {voc}: <b>{who}</b> pide (#{req_id}):",
        "📨 Psst, {voc}… <b>{who}</b> anda buscando algo (#{req_id}):",
        "📨 {Voc}, tengo a <b>{who}</b> esperando en el callejón (#{req_id}):",
    ],
    "admin_new_member": [
        "👤 {Voc}, alguien ha entrado con la contraseña: <b>{who}</b> (<code>{chat_id}</code>), nya.",
        "👤 Cara nueva en el tejado, {voc}: <b>{who}</b> (<code>{chat_id}</code>). Sabía la contraseña.",
    ],
    "admin_no_pending": [
        "Nada pendiente, {voc}. Me echo una siesta entonces. 😺",
        "Libreta vacía, {voc}. Kuro se va a su caja de cartón. 😺",
    ],
    "admin_ep_failed": [
        "❌ {Voc}, se ha torcido el cap. {ep:02d} de <b>{name}</b> (#{req_id}, de {who}):\n"
        "<code>{error}</code>",
    ],
    "admin_movie_failed": [
        "❌ {Voc}, la película <b>{name}</b> (#{req_id}, de {who}) ha fallado:\n<code>{error}</code>",
    ],
    "admin_job_done": [
        "🏁 {Voc}, encargo #{req_id} de {who} terminado: <b>{name}</b> — {done} ok, {failed} fallidos{failed_html}.",
    ],
    "admin_reset": [
        "🧹 Cupos a cero, {voc}. {n} encargos dejan de contar. Borrón y cuenta nueva, nya.",
        "🧹 Hecho, {voc}: arranco la página de la libreta. {n} encargos dejan de contar.",
    ],
    "admin_rejected": [
        "❌ <b>Rechazada.</b> Le he dado con la puerta en los bigotes.",
        "❌ <b>Rechazada.</b> Fsss… fuera de mi tejado.",
    ],
    "admin_approved": ["✅ <b>Aprobada.</b> Marchando, nya."],
    "admin_sending": ["📤 Llevándolo al almacén…", "📤 Kuro sale disparado al almacén…"],
    # Se muestra como alerta: texto plano, sin HTML
    "already_decided": ["Esa ya estaba decidida ({status}), {voc}."],
    # ------------------------------------- Kuro echa de menos al miauestro
    # (nivel 1 = un poco mimoso … nivel 4 = drama total; luego se calla)
    "lonely_1": [
        "🐈‍⬛ Psst… {voc}. Hace {days} que no pasas por el callejón. Kuro solo lo comenta, ¿eh? Nya.",
        "🐾 {Voc}, he dejado la gatera entreabierta por si vuelves. No es que te eche de menos. Bueno, un poco.",
        "🐈‍⬛ Miau. Nada, solo era para ver si seguías ahí, {voc}. Llevas {days} sin dar señales.",
        "😺 Kuro se ha lamido la pata catorce veces esta tarde, {voc}. Es lo que pasa cuando no vienes.",
    ],
    "lonely_2": [
        "😿 {Voc}, ya van {days}. He puesto tu cojín al sol, por si acaso. Sigue vacío.",
        "😿 Le he contado a una paloma que tengo un miauestro. No me ha creído, {voc}. Llevas {days} sin aparecer.",
        "🐈‍⬛ {days} sin ti, {voc}. Kuro empieza a sospechar que tienes otro gato. Fsss…",
        "😿 He repasado la libreta de garra tres veces. Tu nombre sigue ahí, {voc}, pero tú no. Nya…",
    ],
    "lonely_3": [
        "😾 {days}, {voc}. {days}. Un felyne no olvida, ¿sabes? Ni perdona fácilmente. Pero vuelve, ¿vale?",
        "🌧️ Ha llovido en el tejado y nadie me ha abierto la ventana. {days} ya, {voc}. Estoy mojado y ofendido.",
        "😿 Cuando acompañaba a cazadores, al menos me tiraban un trozo de carne asada. Tú, {voc}, llevas {days} sin tirarme ni un «hola».",
        "😾 He tirado un vaso de la mesa. Adrede. Mirándote. Aunque no estuvieras, {voc}. {days} sin vernos.",
    ],
    "lonely_4": [
        "💔 {Voc}… Kuro ha escrito su testamento en la caja de cartón: «todo mi atún para el miauestro que me abandonó». "
        "{days}. No te escribo más, que tengo mi orgullo. Pero aquí sigo.",
        "💔 Ya está, {voc}: me he hecho un ovillo y no pienso moverme hasta que vuelvas. Llevo {days}. "
        "Esta es la última vez que te maúllo… hasta que vuelvas.",
        "💔 {days} sin ti, {voc}. He vuelto a mirar viejos tejados, pero ninguno es como el tuyo. "
        "Kuro se calla ya. Sabes dónde encontrarme.",
    ],
    "lonely_clients": [
        "Por cierto, han pasado {count} encargo(s) mientras no estabas ({who}). Yo los he atendido solito, nya.",
        "Que conste: los clientes sí vienen. {count} encargo(s) estos días ({who}). Tú, no.",
    ],
    "lonely_last_title": [
        "Lo último que me pediste fue <b>{title}</b>. Lo guardo como recuerdo.",
        "Todavía me acuerdo de cuando me pediste <b>{title}</b>. Qué tiempos, nya.",
    ],
    "lonely_back": [
        "😻 ¡{Voc}! ¡Has vuelto! *se frota contra tu pierna* No te había echado de menos ni nada, ¿eh? Nya~",
        "😻 ¡Miauestro! Kuro sabía que volverías. *ronronea a todo volumen*",
        "😸 ¡Por fin, {voc}! Te había guardado el sitio en el sofá. Bueno, lo había usado yo, pero calentito.",
    ],
    "lonely_back_hurt": [
        "😾 Vaya, vaya… mira quién aparece después de {days}. *se da la vuelta y te enseña la cola* "
        "…Vale, vale, ya se me pasa. ¡Bienvenido, {voc}! 😻",
        "😿➡️😻 {days}, {voc}. Iba a hacerme el ofendido, pero no me sale. ¡Qué alegría verte, nya!",
        "😾 Fsss… ¿Ahora vienes, tras {days}? *te mira fijamente* …Está bien. Pero me debes una lata de atún, {voc}.",
    ],
}

# De madrugada (0-7 h) estas variantes se suman a las normales.
NIGHT_HOURS = range(0, 7)
NIGHT_LINES: dict[str, list[str]] = {
    "help_intro_boss": [
        "🐈‍⬛ ¿Despierto a estas horas, {voc}? Mejor: la noche es de los gatos. Dime un anime "
        "(o <code>/pedir nombre</code>) y salgo de ronda por {site}.",
    ],
    "help_intro_client": [
        "🐈‍⬛ Buenas noches, {voc}. A estas horas solo quedamos los gatos y los otakus. Soy "
        "<b>Kuro</b>; dime un anime (o <code>/pedir nombre</code>) y salgo de ronda por {site}.",
    ],
    "searching": [
        "🔎 La noche es mi territorio. Rondando {site} en busca de «{query}»…",
        "🔎 Ojos brillando en la oscuridad… Buscando «{query}» por {site}.",
    ],
    "approved": ["👍 ¡Visto bueno para <b>{title}</b>, {voc}! Buena hora para cazar, nya."],
    "cancelled": ["Como quieras, {voc}. Sigo mi ronda nocturna por los tejados. 🌙"],
    "admin_no_pending": ["Nada pendiente, {voc}. Me voy a maullarle a la luna. 🌙"],
}

# Gestos que Kuro añade de vez en cuando al final de algunos mensajes.
ASIDE_CHANCE = 0.15
ASIDES = [
    "se lame una pata",
    "mueve la cola",
    "se atusa los bigotes",
    "ronronea",
    "bosteza enseñando los colmillos",
    "se estira hasta el último pelo",
    "parpadea despacio",
    "afila las uñas en el sofá",
    "olfatea el aire buscando atún",
    "se acurruca en la caja de cartón",
]
NIGHT_ASIDES = ["los ojos le brillan en la oscuridad", "mira la luna"]
ASIDE_KEYS = {
    "help_intro_boss", "help_intro_client", "welcome_new", "pick", "pick_cards", "cancelled",
    "approved", "approved_boss", "nothing_new", "job_done_all", "movie_done",
    "quota_left", "quota_admin", "admin_no_pending", "sent_to_admin",
}
