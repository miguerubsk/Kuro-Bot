"""
Frases de Kuro (solo datos; la lógica está en persona/__init__.py).

Ficha de personajes: persona/ficha.md (Kuro y el cazador, el miauestro).
Es el canon: cualquier frase que cuente algo del pasado tiene que encajar
con ella. En corto:

- Kuro: gato negro, felyne del miauestro desde Freedom Unite (Aldea Pokke)
  y en todos los juegos después. Casas: Pokke y Elgado; luego Astera y
  Seliana, luego Bherna, y el resto (Wilds incluido) de pasada. Retirados,
  ahora trapichea con anime desde el callejón. Habla con «nya» y juegos
  gatunos, pícaro pero honrado («palabra de felyne») y nocturno. Admira
  muchísimo a su cazador y está orgullosísimo de él: presume de él ante
  los clientes y le recuerda sus hazañas con brillo en los ojos.
- El miauestro (el admin): su cazador. Su arma principal, desde que
  existe, es el hacha cargada (SAED de daño masivo, un set por elemento y
  otro de bruto, contraataques: puntos de guardia y guardia ofensiva).
  También espada larga, cuerno de caza (bufos, tanque) y ballesta pesada
  (escudo acoplado, corta distancia a quemarropa, una apisonadora en
  Sunbreak); prodigio de apoyo con espada y escudo. Cazaba con un grupo.
- No metas más de una o dos referencias por frase y rota el repertorio de
  la ficha.

Todos los textos que ve la gente salen de aquí. Cada clave tiene varias
variantes y se elige una al azar evitando las que han salido hace poco.
Las plantillas son HTML de Telegram:

- {voc} / {Voc}: cómo llama a quien lee (al admin «miauestro», a los
  demás «cliente»…), en minúscula / con mayúscula inicial.
- {site}: un nombre al azar para la web donde se busca (nunca el real).
- {example}: un anime al azar de EXAMPLE_TITLES, para los ejemplos.
- Los valores que se pasan a say() se escapan solos, salvo los que acaban en
  "_html" (ya vienen formateados).
- tests/test_lines.py comprueba que cada variante solo usa los valores que
  el código pasa a esa clave.

Extras:
- NIGHT_LINES: variantes que se suman a las normales de madrugada.
- ASIDES: de vez en cuando, en las claves de ASIDE_KEYS, Kuro añade un gesto
  gatuno al final («<i>se lame una pata</i>»).
- lonely_1 … lonely_N: tantos niveles de soledad como claves haya.
- LORE / BATTLES: de vez en cuando, en las claves de STORY_KEYS, Kuro
  cuenta algo de su vida (a los clientes, según la confianza) o recuerda
  una batallita con el miauestro.
"""

# Cómo llama Kuro al admin y al resto
BOSS_TITLES = ["miauestro", "miauestro", "miauestro", "miauestro-nya"]
CLIENT_TITLES = ["cliente", "cliente", "forastero", "amigo", "cliente-nya", "parroquiano", "socio"]

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
    "el muelle de los piratas",
    "la trastienda del chino de abajo",
    "el rastro digital",
    "la cueva del Tuerto",
    "el puerto de los contrabandistas",
    "los subterráneos del internet",
    "la feria de los gatos pardos",
    "el mercadillo de los martes",
]

# Ejemplos de búsqueda ({example}): títulos en romaji, que es como los nombra la
# web, comprobados en ella (todos dan resultado tal cual). Si se añade alguno,
# que sea así y que exista allí.
EXAMPLE_TITLES = [
    "Sousou no Frieren", "Shingeki no Kyojin", "Kimetsu no Yaiba", "Jujutsu Kaisen",
    "Boku no Hero Academia", "Kusuriya no Hitorigoto", "Yakusoku no Neverland",
    "Kaguya-sama wa Kokurasetai", "Shigatsu wa Kimi no Uso", "Kimi no Na wa",
    "Sen to Chihiro no Kamikakushi", "Mononoke Hime", "Koe no Katachi",
    "Tensei shitara Slime Datta Ken", "Mushoku Tensei", "Kono Subarashii Sekai ni Shukufuku wo!",
    "Yahari Ore no Seishun Love Comedy wa Machigatteiru", "Seishun Buta Yarou", "Dungeon Meshi",
    "Ookami to Koushinryou", "Mahou Shoujo Madoka", "Shinseiki Evangelion",
    "Tengen Toppa Gurren Lagann", "Kaze Tachinu", "Hotaru no Haka", "Tokyo Ghoul", "Chainsaw Man",
    "Oshi no Ko", "Bocchi the Rock!", "Kanojo, Okarishimasu", "Tate no Yuusha no Nariagari",
    "Re:Zero kara Hajimeru Isekai Seikatsu", "Boku no Kokoro no Yabai Yatsu", "Horimiya",
    "Kimi ni Todoke", "Ansatsu Kyoushitsu", "Haikyuu!!", "Kuroko no Basket", "Ao no Exorcist",
    "Nanatsu no Taizai", "Shokugeki no Souma", "Tenki no Ko", "Suzume no Tojimari", "Toradora!",
    "Kekkai Sensen", "Hataraku Maou-sama!", "Sono Bisque Doll wa Koi wo Suru",
    "Ore dake Level Up na Ken", "Kaijuu 8-gou", "Mob Psycho 100", "Fumetsu no Anata e",
    "Vinland Saga", "Mushishi",
]

LINES: dict[str, list[str]] = {
    # ------------------------------------------------------------ ayuda
    "help_intro_boss": [
        "🐈‍⬛ ¡{Voc}! Kuro reportándose, como en Pokke: tú con el arma a la espalda y yo con el barril "
        "bomba listo. Solo que ahora la presa es anime y el campamento es {site}.",
        "🐈‍⬛ Kuro, a sus órdenes, {voc}. Bigotes afilados, zarpas listas y el cascabel que me pusiste "
        "en la ventisca, que no suena pero ahí sigue.",
        "🐈‍⬛ ¡{Voc}, ha vuelto mi cazador! Te he calentado el teclado durmiendo encima, como hacía con "
        "tu cama en Pokke.",
        "🐈‍⬛ Como en Elgado, {voc}: tú señalas la presa en el tablón y Kuro la trae entre los dientes.",
        "🐈‍⬛ El mejor cazador que ha pisado Pokke, Astera y Elgado, en mi chat. Kuro no se acostumbra, "
        "{voc}. ¿Qué cazamos?",
        "🐈‍⬛ ¿Misión nueva, {voc}? Firmas el encargo y Kuro sale del campamento. Hoy sin hacha cargada, "
        "que para esto basta con mis zarpas.",
        "🐈‍⬛ Zarpas limpias, bigotes peinados y cuatro vidas de las siete, todas a tu servicio, {voc}.",
        "🐈‍⬛ A tus órdenes, {voc}. Si sigo vivo es porque siempre ibas tú delante, con el escudo. "
        "¿Qué te traigo?",
    ],
    "help_intro_client": [
        "🐈‍⬛ Bienvenido, {voc}. Soy <b>Kuro</b>: fui el camarada felyne del miauestro en sus años de "
        "cazador y, ya retirado, me dedico a traer anime de {site}, nya.",
        "🐈‍⬛ Nyaa~ Soy <b>Kuro</b>, {voc}. Antes le pasaba barriles bomba a un cazador de rango G; ahora "
        "paso anime de {site}. Pesa menos y explota mucho menos.",
        "🐈‍⬛ Pasa, pasa, {voc}, que entra el frío. Soy <b>Kuro</b>, de la Aldea Pokke, donde el frío "
        "era de verdad. Colgué la mochila de caza y abrí este puestecito en el callejón.",
        "🐈‍⬛ Fufufu… otro cliente con buen gusto. Soy <b>Kuro</b>, {voc}. Mis bigotes aprendieron a "
        "rastrear monstruos junto al miauestro; ahora rastrean capítulos por {site}.",
        "🐈‍⬛ Dicen que un gato negro trae mala suerte, {voc}. Al monstruo que tuviera delante, puede; a "
        "mí me trae clientes. Soy <b>Kuro</b>.",
        "🐈‍⬛ Siéntate, {voc}, que el cajón no muerde. Soy <b>Kuro</b>: me retiré de las cacerías con unas "
        "cuantas vidas de menos y una mochila, que ahora va llena de anime.",
        "🐈‍⬛ Me ha dicho Bigotes, el del puerto, que venías. Soy <b>Kuro</b>, {voc}: el felyne que "
        "cazaba con el miauestro. Mismo olfato, menos fuego.",
        "🐈‍⬛ Bienvenido, {voc}. Soy <b>Kuro</b>, y fui el felyne del miauestro, el mejor cazador de "
        "hacha cargada que verás nunca. Ahora él aprueba y yo traigo el anime de {site}.",
    ],
    # Secciones de /ayuda (las junta ui/texts.py)
    "help_how": [
        "<b>🐾 Cómo se pide</b>\n"
        "1️⃣ Escríbeme el nombre del anime, sin más (o <code>/pedir nombre</code>; en grupos, solo así). "
        "Mejor como lo llaman allí, en romaji: <code>{example}</code>.\n"
        "2️⃣ Te enseño lo que encuentre en fichas: pásalas con ◀️ ▶️ y pulsa la buena. Si tiene varias "
        "temporadas, puedes pedir una o todas de golpe.\n"
        "3️⃣ Miro el almacén: lo que ya tengamos no se vuelve a bajar, y si ya está entero no te gasta carro.\n"
        "4️⃣ El miauestro da el visto bueno y salgo de caza. Te aviso de cada capítulo que llegue y "
        "de cuándo está todo.",
    ],
    "help_how_boss": [
        "<b>🐾 Encargos</b>\n"
        "Escríbeme un nombre (o <code>/pedir nombre</code>), eliges en las fichas y lo tuyo sale al momento, "
        "sin contar carros ni esperar.\n"
        "Lo de los clientes te llega con ✅ / ❌ para que decidas; lo que quede sin decidir está en /pendientes. "
        "Yo les voy contando cómo va cada capítulo.",
    ],
    "help_track": [
        "<b>📡 Animes en emisión</b>\n"
        "Si lo que pides aún se está emitiendo, te pregunto si quieres que lo vigile. Si dices que sí y el "
        "miauestro lo aprueba, cada semana, el día que sale capítulo, lo bajo y te aviso. No gasta "
        "carros, pero puedes vigilar <b>{limit}</b> a la vez como mucho. En /seguimientos los ves y dejas "
        "de seguir los que quieras.",
    ],
    "help_track_boss": [
        "<b>📡 Seguimientos</b>\n"
        "Cuando alguien pide algo en emisión, le ofrezco vigilarlo cada semana y tú lo apruebas o no "
        "(lo tuyo va directo). Solo se mira los días que toca capítulo. A los clientes les aviso yo de cada "
        "capítulo nuevo; a ti te avisa Anime-Automator, como siempre. En /seguimientos están todos.",
    ],
    "help_rules_head": ["<b>📜 El trato</b>"],
    "help_clients_head": ["<b>👥 Clientes</b>"],
    "help_commands_head": ["<b>⌨️ Comandos</b>"],
    "help_admin": [
        "Contigo no hay cuentas, {voc}: sin límites y sin esperar a nadie, nya.",
        "Para ti la casa es libre, {voc}. Pide lo que quieras, que yo no llevo la cuenta, nya.",
        "Tú eres quien me llena el cuenco, {voc}: sin contar carros y sin preguntas.",
        "Las normas son para los clientes, {voc}. Tú pides y Kuro sale; eso es todo.",
        "Contigo, barra libre, {voc}. Como en el campamento: el cazador manda y el felyne obedece.",
    ],
    "help_user": [
        "Normas de la casa, {voc}: tienes <b>{limit} carros por semana</b>, y cada encargo sale en uno. "
        "El miauestro revisa cada encargo antes de que salga. Lo que no se consigue no gasta carro, "
        "palabra de felyne.",
        "Te lo digo clarito, {voc}: como en las misiones, <b>{limit} carros a la semana</b>. Cada encargo "
        "gasta uno, todos con el visto bueno del miauestro. Si un encargo sale mal, el carro vuelve.",
        "El trato es sencillo, {voc}: <b>{limit} carros por semana</b>, un encargo por carro. El miauestro "
        "da el visto bueno y Kuro hace el resto. Si algo falla, no se gasta.",
        "Cuentas claras, {voc}: <b>{limit} carros cada semana</b>. El miauestro mira cada encargo, y lo "
        "que ya tengamos en el almacén no gasta carro. Lo que falle, tampoco.",
        "Aquí se trabaja así, {voc}: me pides, el miauestro dice sí o no, y yo salgo de caza. Tienes "
        "<b>{limit} carros por semana</b>, y si vuelvo con las zarpas vacías, el carro no cuenta.",
        "Como en el gremio, {voc}: <b>{limit} carros y fuera</b>, pero cada semana. Un encargo, un carro; "
        "todas las temporadas de golpe, también uno. Lo que falle no gasta.",
    ],
    "open_warning": [
        "⚠️ Ojo, {voc}: este es un negocio privado. Cada encargo lo mira el miauestro con lupa y puede "
        "decir que no, nya.",
        "⚠️ Que quede claro, {voc}: aquí manda el miauestro. Cada encargo pasa por sus manos y puede "
        "rechazarlo, nya.",
        "⚠️ La puerta está abierta, {voc}, pero detrás está el miauestro. Él decide qué sale y qué no.",
    ],
    "welcome_new": [
        "🔓 ¡Contraseña correcta, nya! Pasa, {voc}, y cierra la gatera al entrar.",
        "🔓 Vienes de parte de alguien, ya veo. Bienvenido al callejón, {voc}~",
        "🔓 Fufufu, sabes la contraseña. Kuro te apunta en su libreta de garra, {voc}. ¡Adentro!",
        "🔓 Contraseña buena. Hueles a cliente de fiar… y un poco a croquetas. Pasa, {voc}, nya.",
        "🔓 Correcto. El Tuerto, que vigila la entrada, te deja pasar. Bienvenido, {voc}.",
        "🔓 Esa es la palabra. Límpiate las patas y entra, {voc}, que acabo de barrer el cartón.",
    ],
    # ---------------------------------------------------------- acceso
    "deny_id": [
        "🔒 Fsss… No te conozco. Si conoces al miauestro, pásale esto: <code>{chat_id}</code>",
        "🔒 Aquí solo se entra con invitación, nya. Tu número de socio sería <code>{chat_id}</code>; "
        "díselo al miauestro.",
        "🔒 Alto ahí, desconocido. Kuro no abre la gatera a cualquiera. Si el miauestro te conoce, "
        "dale este número: <code>{chat_id}</code>",
        "🔒 Huele a forastero… Sin el permiso del miauestro no hay trato. Tu número: <code>{chat_id}</code>",
        "🔒 Las palomas no me han hablado de ti. Si el miauestro te conoce, pásale <code>{chat_id}</code>.",
    ],
    "deny_keyword": [
        "🔒 Fsss… No te conozco. Si te han dado la contraseña: <code>/start contraseña</code>. Si no, "
        "pásale al miauestro tu código de cliente: <code>{chat_id}</code>",
        "🔒 Club privado, nya. Dos formas de entrar: <code>/start contraseña</code>, o que el miauestro "
        "te apunte con tu código, <code>{chat_id}</code>.",
        "🔒 Sin contraseña no hay trato… salvo que el miauestro te conozca. Contraseña: "
        "<code>/start contraseña</code>. Si no la tienes, dale este código: <code>{chat_id}</code>",
        "🔒 El Tuerto no te deja pasar sin la palabra. Si la sabes: <code>/start contraseña</code>. "
        "Si no, que el miauestro te deje pasar con tu código: <code>{chat_id}</code>",
        "🔒 Huele a forastero… Di la contraseña (<code>/start contraseña</code>) o pásale al miauestro "
        "tu código de cliente, <code>{chat_id}</code>, y que él te abra la gatera.",
    ],
    "chat_id": [
        "🐾 El número de este chat es <code>{chat_id}</code>, {voc}.",
        "🐾 Apuntado en mi libreta: este chat es el <code>{chat_id}</code>, {voc}.",
        "🐾 Este rincón del callejón es el <code>{chat_id}</code>, {voc}.",
    ],
    "not_admin": [
        "😼 Buen intento, {voc}, pero eso solo lo toca el miauestro. Nya-nya.",
        "😼 Ni con siete vidas, {voc}. Eso es cosa del miauestro.",
        "😼 Fsss… Esa zarpa quieta, {voc}. Eso es del miauestro.",
        "😼 Kuro es leal, {voc}, y eso solo lo hace el miauestro. Ni por una lata de sardinas.",
        "😼 Eso es como el armario de las chuches, {voc}: solo lo abre el miauestro.",
    ],
    # Se muestra como alerta: texto plano, sin HTML
    "not_authorized": [
        "Fsss… no puedes tocar eso.",
        "Zarpas fuera, nya. Eso no es tuyo.",
        "Fsss… eso no es para ti.",
        "Quieto ahí. Eso es del miauestro.",
    ],
    # -------------------------------------------------------- búsqueda
    "ask_name": [
        "¿Y qué busco, {voc}, bolas de pelo? Dime un nombre, p. ej. <code>/pedir {example}</code>",
        "Necesito un nombre para olfatear, {voc}, nya. Algo como <code>/pedir {example}</code>",
        "Kuro tiene buen olfato, {voc}, pero no lee mentes. Dime algo como <code>/pedir {example}</code>",
        "Con eso no llego ni a la esquina, {voc}. Dame un nombre: <code>/pedir {example}</code>",
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
        "🔎 Le pregunto a la gata Persa del quinto, que lo sabe todo de {site}. «{query}», dices…",
        "🔎 Saltando de contenedor en contenedor por {site} detrás de «{query}»…",
        "🔎 Las palomas de {site} cantan por una gamba. A ver qué saben de «{query}»…",
        "🔎 Como en las misiones de recolección: «{query}», y Kuro rebusca por {site} piedra a piedra.",
    ],
    "search_error": [
        "⚠️ ¡Gatástrofe! {site} no me abre la gatera ahora mismo. Vuelve en un rato, {voc}.",
        "⚠️ Hay redada en {site}, {voc}, y no puedo entrar. Prueba más tarde, nya.",
        "⚠️ La perrera ronda {site} y Kuro no se arriesga, {voc}. Inténtalo dentro de un rato.",
        "⚠️ Fsss… {site} está cerrado a cal y canto. Vuelve luego, {voc}, nya.",
        "⚠️ Han pasado la aspiradora por {site} y no hay quien entre, {voc}. Prueba en un rato.",
        "⚠️ El perro del vecino se ha plantado en la puerta de {site}. Mejor volvemos luego, {voc}.",
    ],
    "not_found": [
        "😿 Ni rastro de «{query}» en {site}, {voc}. Prueba con el título en romaji "
        "(p. ej. <i>{example}</i>) o con menos palabras.",
        "😿 Mis contactos de {site} no saben nada de «{query}», nya. A veces lo conocen por el "
        "nombre en romaji (<i>{example}</i>) o con menos palabras.",
        "😿 He husmeado {site} de arriba abajo y de «{query}» nada, {voc}. ¿Probamos con el "
        "nombre en romaji (<i>{example}</i>) o algo más corto?",
        "😿 «{query}»… Ese pescado no nada por {site}, {voc}. Prueba con el título japonés en "
        "letras latinas (<i>{example}</i>) o con menos palabras.",
        "😿 He vaciado todos los contenedores de {site} y de «{query}» ni la raspa, {voc}. "
        "Prueba en romaji (<i>{example}</i>) o con una palabra menos.",
    ],
    "alias_hint": [
        "🐾 Por {site} a «{query}» no lo conocen así, pero mis contactos dicen que es <b>{alias}</b>, nya.",
        "🐾 «{query}», ¿eh? Por estos callejones lo llaman <b>{alias}</b>. ¡Miauravilloso, {voc}!",
        "🐾 Ah, te refieres a <b>{alias}</b>. En {site} lo tienen con ese nombre, nya.",
        "🐾 Psst, {voc}: en {site} «{query}» va de incógnito como <b>{alias}</b>. Pero a Kuro no se le escapa.",
        "🐾 La gata Persa me ha soplado que «{query}» aquí se llama <b>{alias}</b>, {voc}.",
    ],
    "pick": [
        "Esto es lo que circula por {site}, {voc}. ¿Cuál te llevas?",
        "Mira lo que he pescado, {voc}~ ¿Cuál es el bueno?",
        "Fufufu, tengo género. ¿Cuál quieres, {voc}?",
        "Abro la gabardina y… ¡tachán! Elige, {voc}, nya.",
        "Todo fresco, recién sacado de {site}. ¿Cuál te pongo, {voc}?",
        "Te lo dejo todo en fila, como los ratones de trapo, {voc}. ¿Cuál?",
        "Género de primera, {voc}. Señala con la zarpa el que quieras.",
    ],
    "pick_cards": [
        "Esto es lo que circula por {site}, {voc}. Te enseño las fichas una a una: pasa con ◀️ ▶️ y dime cuál te llevas.",
        "Mira lo que he pescado, {voc}~ Cada uno con su portada y su historia. ◀️ ▶️ para hojear.",
        "Fufufu, abro la gabardina y te enseño el género ficha a ficha, {voc}. Pasa con ◀️ ▶️, nya.",
        "Todo fresco, recién sacado de {site}. Hojea con ◀️ ▶️ y elige, {voc}.",
        "Kuro te pone el catálogo delante, {voc}: portada, de qué va y cuántos capítulos. ◀️ ▶️ para pasar.",
        "Escaparate abierto, {voc}. ◀️ ▶️ para mirar y «Pedir este» cuando te enamores, nya.",
        "Como en la tienda de la plaza del gremio: ficha a ficha, {voc}. ◀️ ▶️ y eliges.",
    ],
    # /descargados (solo el admin)
    "history_mine": [
        "📜 Tu cuaderno de caza, {voc}: <b>{count}</b> presa(s) traídas a la madriguera.",
        "📜 Lo que me has encargado tú, {voc}: <b>{count}</b>. Buen ojo, nya.",
        "📜 Repaso de tu botín, {voc}: <b>{count}</b>. Kuro lo apunta todo, hasta lo que pides a deshoras.",
        "📜 El inventario del miauestro: <b>{count}</b>. Ordenadito, como mis bigotes.",
        "📜 <b>{count}</b> misiones completadas para ti, {voc}. Si fuera el gremio, ya tendrías medalla.",
    ],
    "history_empty_mine": [
        "📜 Tu lista está vacía, {voc}. ¿Me tienes a dieta?",
        "📜 Ni un encargo tuyo apuntado, {voc}. El cuaderno huele a nuevo, nya.",
        "📜 Nada a tu nombre, {voc}. Kuro empieza a aburrirse de cazar para otros.",
    ],
    "history_client_one": [
        "📜 {who} solo se ha llevado uno. Cliente de paso, como los gatos callejeros.",
        "📜 {who}: un encargo y gracias. Le tengo fichado, por si vuelve, nya.",
        "📜 Una sola pieza para {who}. Prueba la mercancía antes de hacerse fijo, fufufu.",
        "📜 {who} se llevó uno y desapareció como un gato por un tejado.",
    ],
    "history_client_few": [
        "📜 {who}: <b>{count}</b> encargos. Va cogiendo confianza, nya.",
        "📜 {who} ya se ha llevado <b>{count}</b>. Le empiezo a reconocer por las pisadas.",
        "📜 <b>{count}</b> para {who}. Si sigue así, le guardo un cojín en el mostrador.",
        "📜 {who}, <b>{count}</b> encargos. Ya no le bufo cuando entra.",
    ],
    "history_client_many": [
        "📜 {who} es cliente de la casa: <b>{count}</b> encargos. Ya le guardo sitio junto al radiador.",
        "📜 <b>{count}</b> encargos de {who}. Cliente VIP: Vale Infinitas Pescaditos, nya.",
        "📜 {who} lleva <b>{count}</b>. A este paso le pongo su nombre a una caja de cartón.",
        "📜 <b>{count}</b> para {who}. Le dejo amasar en mi manta, que es lo máximo que doy.",
    ],
    "history_client_waiting": [
        "📜 {who} todavía no ha estrenado nada: lo suyo aún viene de camino.",
        "📜 A {who} aún no le ha llegado nada, nya. Lo suyo está en el saco.",
        "📜 {who} espera su primera pieza. Va en el carro de vuelta al campamento.",
    ],
    "history_empty_client": [
        "📜 {who} aún no se ha llevado nada. Mira mucho y compra poco, nya.",
        "📜 Nada a nombre de {who} todavía. Olfatea el escaparate y se va.",
        "📜 {who} todavía no ha pedido nada. Viene, mira y se va, como el gato del vecino.",
    ],
    "history_in_progress": [
        "⏳ <b>En camino</b> (aún bajando, nya):",
        "⏳ <b>En el saco</b>, todavía llegando:",
        "⏳ <b>De camino al campamento</b>:",
    ],
    "cancelled": [
        "Como quieras, {voc}. Me vuelvo a mi caja de cartón. 🐈‍⬛",
        "Trato cancelado. Sin rencores, nya.",
        "Vale, {voc}. Kuro guarda la mercancía y se echa una siesta. 🐈‍⬛",
        "Otra vez será, {voc}. La gatera queda abierta, nya.",
        "Recogido. Me voy a perseguir el rayo de sol del pasillo, {voc}. 🐈‍⬛",
        "Sin problema, {voc}. Vuelvo a mi puesto en la farola de la esquina.",
    ],
    "expired": [
        "⚠️ Esa lista se ha quedado más vieja que el pienso de ayer, {voc}. Pídemelo otra vez.",
        "⚠️ Esa mercancía ya no está en el escaparate, {voc}. Vuelve a buscarlo, nya.",
        "⚠️ Eso se lo llevó el camión de la basura, {voc}. Búscalo de nuevo.",
    ],
    "reading_post": [
        "⏳ Echando un ojo a la mercancía: <b>{title}</b>…",
        "⏳ Inspeccionando <b>{title}</b> con lupa de detective, nya…",
        "⏳ Olisqueando <b>{title}</b> para ver si está fresco…",
        "⏳ Un momento, {voc}, que reviso <b>{title}</b> pata por pata…",
        "⏳ Dándole golpecitos a <b>{title}</b> con la zarpa, a ver si se mueve…",
    ],
    "post_error": [
        "⚠️ No he podido abrir la ficha de ese anime, {voc}. Prueba en un rato, nya.",
        "⚠️ La ficha de ese anime se me ha atascado en las zarpas, {voc}. Inténtalo luego.",
        "⚠️ Esa ficha se me ha caído detrás del sofá, {voc}. Prueba otra vez en un rato.",
    ],
    "no_link": [
        "😿 He encontrado <b>{title}</b>, pero no hay enlace de descarga, {voc}. Ni un gato puede "
        "sacar algo de donde no hay.",
        "😿 <b>{title}</b> está en el escaparate, pero no hay forma de llevárselo, {voc}. "
        "Ni con siete vidas, nya.",
        "😿 <b>{title}</b> es como el pez del acuario, {voc}: se ve pero no se toca. No hay enlace.",
    ],
    # --------------------------------------- comprobación de la biblioteca
    "checking_library": [
        "📚 Un momento, {voc}: miro si <b>{title}</b> ya está en el almacén…",
        "📚 Repasando las estanterías del almacén por si ya tenemos <b>{title}</b>…",
        "📚 Antes de salir de caza, Kuro mira la despensa: ¿tenemos ya <b>{title}</b>?",
        "📚 Rebuscando en las cajas del trastero por si <b>{title}</b> ya está aquí, {voc}…",
    ],
    "library_complete": [
        "😸 ¡Buenas noticias, {voc}! <b>{title}</b> ya está entero en el almacén ({have} capítulos). "
        "No hace falta encargo y tus carros siguen intactos, nya.",
        "😸 Fufufu, <b>{title}</b> ya duerme en nuestras estanterías, {voc}: {have} capítulos, "
        "todos en su sitio. Esto no gasta carro.",
        "😸 No hace falta salir de caza, {voc}: <b>{title}</b> ya está completito en el almacén "
        "({have} capítulos). Tus carros, sin tocar.",
        "😸 Ya lo tenemos, {voc}: <b>{title}</b>, {have} capítulos. Te ahorras el encargo y yo el paseo.",
    ],
    "library_movie": [
        "😸 La película <b>{title}</b> ya está en el almacén, {voc}. No hace falta encargo y tus "
        "carros siguen intactos, nya.",
        "😸 <b>{title}</b> ya está en la estantería de pelis, {voc}. Esto no gasta carro.",
        "😸 <b>{title}</b> ya la tenemos, {voc}. Palomitas sí; encargo no hace falta.",
    ],
    "library_busy": [
        "😸 Lo que falta de <b>{title}</b> ya viene de camino por otro encargo, {voc}. "
        "No hace falta pedirlo otra vez, y tus carros siguen intactos.",
        "😸 Otro gato ya va a por <b>{title}</b>, {voc}. Llegará solo; esto no gasta carro, nya.",
        "😸 <b>{title}</b> ya viene en el carro, {voc}. Llegará sin que gastes nada.",
    ],
    # se añade a "sent_to_admin" cuando ya hay parte en la biblioteca
    "library_partial": [
        "\n📚 Ya tenemos {have} de {available} capítulos: el encargo es solo por los {count} "
        "que faltan ({ranges}).",
        "\n📚 En el almacén ya hay {have} de {available}; Kuro solo traería los {count} que faltan "
        "({ranges}).",
        "\n📚 Tenemos {have} de {available}. Solo voy a por los {count} que faltan ({ranges}).",
    ],
    # se añade a "sent_to_admin" cuando lo que falta ya está, pero en peor calidad
    "library_upgrade": [
        "\n📀 Ya lo tenemos, pero en peor calidad: Kuro lo cambia por el bueno y esto <b>no gasta carro</b>.",
        "\n📀 En el almacén está en una versión pochita; la cambio por la buena sin gastarte carro, nya.",
        "\n📀 Lo que hay está más rayado que mi poste de arañar: lo cambio por el bueno y <b>no gasta carro</b>.",
    ],
    # ------------------------------------------------- todas las temporadas
    "pick_seasons": [
        "\n📦 Hay varias temporadas: puedes llevártelas todas por <b>un solo encargo</b>.",
        "\n📦 Oferta de la casa: todas las temporadas juntas cuentan como <b>un encargo</b>, nya.",
        "\n📦 Varias temporadas a la vista: el lote entero cuenta como <b>un encargo</b>.",
    ],
    "bundle_reading": [
        "⏳ Reuniendo todas las temporadas de <b>{title}</b> y mirando qué hay ya en el almacén…",
        "⏳ Kuro va estantería por estantería con las temporadas de <b>{title}</b>…",
        "⏳ Metiendo en el saco las temporadas de <b>{title}</b>, una a una…",
    ],
    "bundle_all_have": [
        "😸 Todas las temporadas de <b>{title}</b> ya están en el almacén, {voc}. No hace falta encargo "
        "y tus carros siguen intactos.",
        "😸 Nada que cazar: <b>{title}</b> ya está entero, todas sus temporadas. Tus carros, intactos, nya.",
        "😸 <b>{title}</b>, de la primera temporada a la última, ya está aquí, {voc}. No gastas nada.",
    ],
    "bundle_sent": [
        "📨 ¡Lote apuntado, {voc}! <b>{title}</b>: {items_html}\nVa en <b>un solo carro</b>. "
        "Se lo paso al miauestro y te aviso, nya.\nTe quedan {left} de {limit} carros esta semana.",
        "📨 Todo al saco: <b>{title}</b> ({items_html}). Un solo carro, palabra de felyne. "
        "Ahora decide el miauestro.\nTe quedan {left} de {limit} carros esta semana.",
        "📨 Lote de <b>{title}</b> ({items_html}) en el buzón del miauestro, {voc}. Va en un solo carro.\n"
        "Te quedan {left} de {limit} carros esta semana.",
    ],
    "bundle_skipped": [
        "\n😸 Ya en el almacén (no se piden): {items_html}.",
        "\n😸 Estas ya las tenemos y no entran en el lote: {items_html}.",
        "\n😸 Fuera del lote, que ya están aquí: {items_html}.",
    ],
    "bundle_rejected": [
        "❌ El miauestro ha dicho que no al lote de <b>{title}</b>, {voc}. No gasta carro, nya.",
        "❌ Lote de <b>{title}</b> denegado. Tranquilo, {voc}, tus carros siguen intactos.",
        "❌ Esta vez no, {voc}: el miauestro rechaza el lote de <b>{title}</b>. No te cuesta nada.",
    ],
    "admin_bundle_request": [
        "📨 {Voc}, <b>{who}</b> quiere <b>todas las temporadas</b> (lote #{bundle}, va en un solo carro):",
        "📨 Encargo gordo, {voc}: <b>{who}</b> se lleva el lote completo (#{bundle}, un solo carro):",
        "📨 {Voc}, <b>{who}</b> quiere la serie entera de una tacada (lote #{bundle}):",
    ],
    "already_pending": [
        "⏳ Ya tienes un encargo de <b>{title}</b> en marcha, {voc}. Paciencia, que no soy mago… "
        "solo un gato, nya.",
        "⏳ <b>{title}</b> ya está en mi libreta, {voc}. Kuro no olvida un encargo, palabra de felyne.",
        "⏳ Eso ya me lo pediste, {voc}: <b>{title}</b> está en marcha. No me hagas correr dos veces.",
    ],
    # ------------------------------------------------------------- cupo
    "no_quota": [
        "⛔ Tres carros y fuera, {voc}… bueno, {limit}: ya los has gastado todos esta semana.{when_html}",
        "⛔ No te quedan carros, {voc}: {limit} por semana y ya han salido todos. Nya.{when_html}",
        "⛔ Los {limit} carros de la semana están en el camino, {voc}. Hay que esperar a que vuelvan.{when_html}",
        "⛔ Ni un carro más, {voc}, que el miauestro me deja sin sardinas. Ya llevas {limit} esta semana.{when_html}",
        "⛔ Misión fallida, {voc}: {limit} carros esta semana, y ya han salido todos.{when_html}",
    ],
    "no_quota_when": [
        " Vuelve el {date}.",
        " Tendrás hueco el {date}, nya.",
        " Te espero el {date} en la esquina de siempre.",
        " El {date} vuelve a haber carro, nya.",
    ],
    "quota_left": [
        "Te quedan <b>{left}</b> de {limit} carros esta semana, {voc}.",
        "Cuenta de la semana, {voc}: <b>{left}</b> de {limit} carros listos para salir, nya.",
        "Según mi libreta de garra, {voc}, te quedan <b>{left}</b> carros de {limit} esta semana.",
        "Puedes gastar <b>{left}</b> carros más esta semana, {voc} (de {limit}).",
        "En el establo hay <b>{left}</b> de tus {limit} carros, {voc}. Úsalos bien.",
    ],
    "quota_admin": [
        "♾️ ¿Límite? ¿Para ti, {voc}? Nyaaa, ni hablar.",
        "♾️ Tú no tienes límite, {voc}. Pide sin miedo.",
        "♾️ ¿Contarte los encargos a ti, {voc}? Kuro no está tan loco, nya.",
        "♾️ Tus carros son como mis siestas, {voc}: infinitos.",
        "♾️ ¿Carros, tú? El cazador que nunca se rindió por tres carros no necesita contarlos, {voc}.",
    ],
    # ---------------------------------------------------------- petición
    "sent_to_admin": [
        "📨 Encargo de <b>{title}</b>{label} apuntado, {voc}. Se lo paso al miauestro y te aviso cuando "
        "diga algo, nya.\nTe quedan {left} de {limit} carros esta semana.",
        "📨 ¡Apuntado en mi libreta de garra! <b>{title}</b>{label}. Ahora decide el miauestro; "
        "ya te contaré, {voc}.\nTe quedan {left} de {limit} carros esta semana.",
        "📨 <b>{title}</b>{label}: encargo en el buzón del miauestro, {voc}. En cuanto mueva un bigote, "
        "te aviso.\nTe quedan {left} de {limit} carros esta semana.",
        "📨 Le llevo <b>{title}</b>{label} al miauestro en la boca, como un ratón de regalo. Te aviso, {voc}.\n"
        "Te quedan {left} de {limit} carros esta semana.",
    ],
    "admin_unreachable": [
        "⚠️ No consigo localizar al miauestro, {voc}. Prueba más tarde (no te gasta carro).",
        "⚠️ El miauestro no contesta, {voc}. Vuelve luego, que esto no te gasta carro, nya.",
        "⚠️ He llamado a la puerta del miauestro y nada, {voc}. Prueba luego; no te cuesta carro.",
    ],
    "sending": [
        "📤 Llevando el encargo de <b>{title}</b>{label} al almacén… nya.",
        "📤 Allá va <b>{title}</b>{label}, directo al almacén. En un santiamiau…",
        "📤 <b>{title}</b>{label} bien sujeto entre los dientes, camino del almacén…",
        "📤 <b>{title}</b>{label} cargado en el carro. ¡Arre!",
    ],
    "approved": [
        "👍 ¡El miauestro ha dado el visto bueno a <b>{title}</b>, {voc}! Miaugnífico.",
        "👍 ¡Trato hecho, nya! <b>{title}</b> va para dentro.",
        "👍 ¡Miauravilloso, {voc}! El miauestro dice que sí a <b>{title}</b>.",
        "👍 ¡Luz verde para <b>{title}</b>, {voc}! Kuro sale de caza.",
        "👍 El miauestro ha asentido, {voc}. <b>{title}</b>, allá voy.",
        "👍 ¡Aprobado! <b>{title}</b> sale del gremio con su sello, {voc}.",
    ],
    "approved_boss": [
        "👍 ¡A la orden, {voc}! <b>{title}</b> va para dentro.",
        "👍 ¡Marchando <b>{title}</b>, {voc}! Nya.",
        "👍 Dicho y hecho, {voc}: <b>{title}</b> en camino.",
        "👍 Misión aceptada, {voc}: <b>{title}</b>. Kuro sale del campamento.",
    ],
    "queued": [
        "📦 Hay {count} capítulo(s) en camino ({ranges}). Te aviso de cada uno según llegue, nya.",
        "📦 {count} capítulo(s) en la cola ({ranges}). Te los voy contando uno a uno, {voc}.",
        "📦 {count} capítulo(s) en el saco ({ranges}). Kuro te avisa de cada pieza que cobre.",
        "📦 {count} capítulo(s) en ruta ({ranges}). Cada vez que llegue uno, maullido al canto.",
    ],
    "queued_untracked": [
        "📦 {count} capítulo(s) en camino ({ranges}).",
        "📦 {count} capítulo(s) en ruta ({ranges}).",
    ],
    "movie_queued": [
        "🎬 La película ya está en camino, {voc}. Te aviso en cuanto esté en su sitio, nya.",
        "🎬 Película en la cola. Prepárate las palomitas, {voc}… y unas gambas para mí.",
        "🎬 La peli va de camino, {voc}. Ve buscando sitio en el sofá, que Kuro se pide el cojín.",
        "🎬 Película en el carro, {voc}. Te maúllo cuando llegue.",
    ],
    "rejected": [
        "❌ El miauestro ha dicho que no a <b>{title}</b>, {voc}. No te lo cuento como encargo, nya.",
        "❌ <b>{title}</b>: denegado por el miauestro. Tranquilo, {voc}, no gasta carro.",
        "❌ Mala suerte, {voc}: el miauestro no quiere <b>{title}</b>. Tus carros siguen intactos, nya.",
        "❌ El miauestro ha arrugado el bigote con <b>{title}</b>, {voc}. Esta vez no; no te cuesta nada.",
    ],
    "nothing_new": [
        "😸 <b>{title}</b> ya está entero en la colección, {voc}. No te lo cobro, nya.",
        "😸 ¡Ya lo tenemos todo! <b>{title}</b> está completito. Encargo gratis, {voc}.",
        "😸 <b>{title}</b> ya duerme en el almacén, {voc}, de la cabeza a la cola. Esto no se cobra.",
        "😸 <b>{title}</b> ya estaba aquí, {voc}. Me ahorras el paseo; no te cobro nada.",
    ],
    "already_downloading": [
        "😸 <b>{title}</b> ya se está descargando por otro lado, {voc}. No te lo cobro.",
        "😸 Otro gato ya va a por <b>{title}</b>, {voc}. Para ti, gratis, nya.",
        "😸 <b>{title}</b> ya viene en el carro por otro encargo, {voc}. Gratis.",
    ],
    "tech_failure": [
        "⚠️ ¡Gatástrofe técnica con <b>{title}</b>! Habrá que echarle un ojo; de momento no gasta carro, {voc}.",
        "⚠️ Se me ha enredado el ovillo con <b>{title}</b>, {voc}. Toca revisarlo; no te cuenta como encargo.",
        "⚠️ <b>{title}</b> ha hecho saltar un barril bomba en el almacén, {voc}. Hay que revisarlo; no te cuesta carro.",
    ],
    "airing": [
        "📺 Está <b>en emisión</b>{progress}: te traigo lo que ya ha salido. Lo nuevo no llega solo, "
        "salvo que me pidas que lo vigile, {voc}.",
        "📺 Ojo, que está <b>en emisión</b>{progress}: Kuro trae lo que hay. Para lo que salga "
        "después, tendrías que pedirme que lo vigile, {voc}.",
        "📺 Sigue <b>en emisión</b>{progress}, {voc}: traigo lo publicado. Lo nuevo no vendrá "
        "solo, a menos que me pongas de guardia.",
    ],
    # ------------------------------------------------ progreso por capítulo
    "ep_done": [
        "✅ <b>{name}</b> — capítulo {ep:02d} entregado ({n}/{total}). Nya~",
        "🐾 Capítulo {ep:02d} de <b>{name}</b> listo ({n}/{total}).",
        "✅ ¡Pesca del día! El {ep:02d} de <b>{name}</b> ya está ({n}/{total}).",
        "🐟 Otro más para la cesta: <b>{name}</b> {ep:02d} ({n}/{total}).",
        "✅ <b>{name}</b> {ep:02d}, cazado y en su sitio ({n}/{total}).",
        "🐾 Ronroneo de satisfacción: <b>{name}</b> {ep:02d} entregado ({n}/{total}).",
        "✅ <b>{name}</b> {ep:02d} dejado en el felpudo, como un buen regalo gatuno ({n}/{total}).",
        "🐾 <b>{name}</b> {ep:02d}: cazado al primer salto ({n}/{total}).",
        "✅ Uno menos: <b>{name}</b> {ep:02d} ({n}/{total}).",
    ],
    "ep_retry": [
        "⏳ El capítulo {ep:02d} de <b>{name}</b> se me resiste, {voc}. Lo vuelvo a intentar en {delay}.",
        "⏳ Bufff, el {ep:02d} de <b>{name}</b> no se deja cazar. Reintento en {delay}, nya.",
        "⏳ El {ep:02d} de <b>{name}</b> se ha escondido debajo del sofá. Vuelvo a por él en {delay}.",
        "⏳ El {ep:02d} de <b>{name}</b> se ha subido a un árbol. Le espero abajo; vuelvo a probar en {delay}.",
    ],
    "ep_fallback": [
        "🔄 El capítulo {ep:02d} de <b>{name}</b> lo traigo por los tejados (torrent). Tardará algo más.",
        "🔄 La puerta principal está cerrada para el {ep:02d} de <b>{name}</b>: voy por los tejados "
        "(torrent). Tardará algo más, nya.",
        "🔄 Para el {ep:02d} de <b>{name}</b> tiro por las alcantarillas (torrent). Algo más lento, pero llega.",
    ],
    "ep_failed": [
        "😿 El capítulo {ep:02d} de <b>{name}</b> no ha podido ser, {voc}. Nya…",
        "😿 Se me ha escapado el {ep:02d} de <b>{name}</b>. Lo siento, {voc}.",
        "😿 El {ep:02d} de <b>{name}</b> se ha escurrido entre las zarpas, {voc}. Kuro lo siente.",
        "😿 El {ep:02d} de <b>{name}</b> se ha perdido por el camino, {voc}. Me he quedado sin esa presa.",
    ],
    "job_done_all": [
        "🎉 ¡<b>{name}</b> completo, {voc}! {done} capítulo(s) entregados. ¡Miaugnífico!",
        "🎉 Entrega terminada: <b>{name}</b>, {done} capítulo(s). Que lo disfrutes, {voc}~ nya.",
        "🎉 ¡Cacería completada! <b>{name}</b>: {done} capítulo(s), ni uno se ha escapado. "
        "Esto se celebra con boquerones, {voc}.",
        "🎉 <b>{name}</b> entero en el almacén, {voc}: {done} capítulo(s). Kuro no falla, nya.",
        "🎉 ¡Misión cumplida! <b>{name}</b>, {done} capítulo(s). Vuelta al campamento con el saco lleno, {voc}.",
        "🎉 <b>{name}</b>: los {done} capítulo(s), sin perder ni una vida por el camino, {voc}.",
    ],
    "job_done_partial": [
        "🏁 <b>{name}</b> terminado, {voc}: {done} capítulo(s) entregados y {failed} que no han "
        "podido ser ({failed_ranges}).",
        "🏁 Cacería de <b>{name}</b> acabada, {voc}: {done} capítulo(s) en el saco y {failed} "
        "que se han escapado ({failed_ranges}). Nya…",
        "🏁 <b>{name}</b>: {done} capítulo(s) traídos, {voc}. Se me resistieron {failed} ({failed_ranges}).",
    ],
    "job_failed": [
        "😿 No he conseguido ni un capítulo de <b>{name}</b>, {voc}. Este encargo no te gasta "
        "carro, nya.",
        "😿 Vuelvo con las zarpas vacías: ni un capítulo de <b>{name}</b>, {voc}. No te lo cobro, "
        "palabra de felyne.",
        "😿 <b>{name}</b> me ha ganado esta vez, {voc}: ni un capítulo. No te gasta carro.",
    ],
    "movie_done": [
        "🎬 ¡<b>{name}</b> ya está en su sitio, {voc}! A disfrutar, nya~",
        "🎬 Película entregada: <b>{name}</b>. ¡Miauravilloso! Palomitas para ti, salmón para mí.",
        "🎬 <b>{name}</b> en el almacén, {voc}. Apaga la luz, que empieza la función, nya.",
        "🎬 <b>{name}</b> lista, {voc}. Kuro se queda a verla contigo… desde encima de la tele.",
    ],
    "movie_retry": [
        "⏳ La película <b>{name}</b> se resiste, {voc}. Lo vuelvo a intentar en {delay}.",
        "⏳ <b>{name}</b> se hace de rogar, {voc}. Kuro vuelve a la carga en {delay}, nya.",
        "⏳ <b>{name}</b> se ha escondido en el transportín y no sale, {voc}. Pruebo otra vez en {delay}.",
    ],
    "movie_failed": [
        "😿 No he podido traer <b>{name}</b>, {voc}. No te gasta carro, nya.",
        "😿 <b>{name}</b> se me ha escapado, {voc}. No te la cobro, palabra de felyne.",
        "😿 <b>{name}</b> no ha querido venir, {voc}. Esto no te cuesta carro.",
    ],
    "movie_already": [
        "😸 La película <b>{title}</b> ya está en la colección, {voc}. No te lo cobro.",
        "😸 <b>{title}</b> ya está en la estantería, {voc}. Gratis, nya.",
        "😸 <b>{title}</b> ya estaba aquí, {voc}. No te cobro nada.",
    ],
    # --------------------------------------------------- mensajes al admin
    "admin_request": [
        "📨 ¡{Voc}, nya! <b>{who}</b> quiere un encargo (#{req_id}):",
        "📨 Cliente en la puerta, {voc}: <b>{who}</b> pide (#{req_id}):",
        "📨 Psst, {voc}… <b>{who}</b> anda buscando algo (#{req_id}):",
        "📨 {Voc}, tengo a <b>{who}</b> esperando en el callejón (#{req_id}):",
        "📨 {Voc}, encargo nuevo en el tablón del gremio, de <b>{who}</b> (#{req_id}):",
        "📨 {Voc}, <b>{who}</b> ha dejado una nota bajo la puerta (#{req_id}):",
    ],
    "welcome_added": [
        "🔓 ¡El miauestro ha respondido por ti, {voc}! Kuro te apunta en su libreta de garra. Pasa, nya.",
        "🔓 Vienes de parte del miauestro: con eso basta. Bienvenido al callejón, {voc}~",
        "🔓 El Tuerto ya tiene tu cara apuntada, {voc}: el miauestro te ha dejado pasar. ¡Adentro!",
    ],
    "admin_added": [
        "🔓 Hecho, {voc}: <b>{who}</b> (<code>{chat_id}</code>) ya puede pedir. Le he dado la bienvenida.",
        "🔓 Apuntado en la libreta: <b>{who}</b> (<code>{chat_id}</code>). Ya le he abierto la gatera, {voc}.",
    ],
    "admin_add_already": [
        "😼 <code>{chat_id}</code> ya puede entrar, {voc}. No hace falta apuntarlo dos veces.",
        "😼 Ese ya está en la libreta, {voc} (<code>{chat_id}</code>).",
    ],
    "admin_add_open": [
        "😼 Ahora mismo la puerta está abierta para todos, {voc}: no hace falta dar de alta a nadie.",
    ],
    "admin_new_member": [
        "👤 {Voc}, alguien ha entrado con la contraseña: <b>{who}</b> (<code>{chat_id}</code>), nya.",
        "👤 Cara nueva en el callejón, {voc}: <b>{who}</b> (<code>{chat_id}</code>). Sabía la contraseña.",
        "👤 {Voc}, el Tuerto ha dejado pasar a <b>{who}</b> (<code>{chat_id}</code>). Traía la contraseña.",
    ],
    "admin_no_pending": [
        "Nada pendiente, {voc}. Me echo una siesta entonces. 😺",
        "Libreta vacía, {voc}. Kuro se va a su caja de cartón. 😺",
        "Ni un encargo esperando, {voc}. Me voy a vigilar a las palomas. 😺",
        "Todo al día, {voc}. Me tumbo en el radiador hasta nueva orden. 😺",
    ],
    "admin_ep_failed": [
        "❌ {Voc}, se ha torcido el cap. {ep:02d} de <b>{name}</b> (#{req_id}, de {who}):\n"
        "<code>{error}</code>",
        "❌ {Voc}, el cap. {ep:02d} de <b>{name}</b> no ha llegado (#{req_id}, de {who}):\n"
        "<code>{error}</code>",
    ],
    "admin_movie_failed": [
        "❌ {Voc}, la película <b>{name}</b> (#{req_id}, de {who}) ha fallado:\n<code>{error}</code>",
        "❌ {Voc}, no he podido traer la película <b>{name}</b> (#{req_id}, de {who}):\n<code>{error}</code>",
    ],
    "admin_job_done": [
        "🏁 {Voc}, encargo #{req_id} de {who} terminado: <b>{name}</b> — {done} ok, {failed} fallidos{failed_html}.",
        "🏁 {Voc}, cerrado el #{req_id} de {who}: <b>{name}</b> — {done} ok, {failed} fallidos{failed_html}.",
    ],
    "admin_reset": [
        "🧹 Carros devueltos al establo, {voc}. {n} encargos dejan de contar. Borrón y cuenta nueva, nya.",
        "🧹 Hecho, {voc}: arranco la página de la libreta. {n} encargos dejan de gastar carro.",
        "🧹 Barrido, {voc}: {n} encargos fuera de la cuenta. Carros como nuevos.",
    ],
    "admin_rejected": [
        "❌ <b>Rechazada.</b> Le he dado con la puerta en los bigotes.",
        "❌ <b>Rechazada.</b> Fsss… fuera de mi callejón.",
        "❌ <b>Rechazada.</b> Encargo a la papelera, junto a las raspas.",
    ],
    "admin_approved": [
        "✅ <b>Aprobada.</b> Marchando, nya.",
        "✅ <b>Aprobada.</b> Kuro sale de caza.",
        "✅ <b>Aprobada.</b> Al saco.",
    ],
    "admin_sending": [
        "📤 Llevándolo al almacén…",
        "📤 Kuro sale disparado al almacén…",
        "📤 Cargando el carro…",
    ],
    # ------------------------------------------------ seguimiento semanal
    "track_offer": [
        "📡 <b>{title}</b> sigue en emisión, {voc}. ¿Quieres que me aposte cada semana en {site} "
        "y lo traiga según vaya saliendo? Solo vigilo los días que toca, nya.",
        "📡 {Voc}, <b>{title}</b> aún no ha terminado. ¿Me quedo de guardia en el tejado y te "
        "traigo cada capítulo nuevo cuando salga? Te maúllo cuando llegue cada uno.",
        "📡 <b>{title}</b> sigue saliendo por capítulos. Puedo echarle un ojo cada semana, {voc}: "
        "el día que toca me asomo a {site} y me lo traigo. ¿Te lo vigilo?",
        "📡 ¿Seguimiento semanal de <b>{title}</b>, {voc}? Kuro hace guardia el día del capítulo, "
        "como con los barriles de pesca: paciencia y zarpa rápida.",
    ],
    "track_ep_done": [
        "📡 ¡Capítulo nuevo, {voc}! <b>{name}</b> {ep:02d} ya está en el almacén. La guardia ha dado fruto, nya.",
        "📡 Kuro bajó del tejado con algo en la boca: <b>{name}</b> {ep:02d}, recién salido. Para ti, {voc}.",
        "📡 Guardia cumplida, {voc}: <b>{name}</b> {ep:02d} acaba de llegar.",
        "📡 ¡Pesca de la semana! <b>{name}</b> {ep:02d} ya está en su sitio, {voc}.",
        "📡 Psst, {voc}… <b>{name}</b> {ep:02d}. Recién cazado y entregado. Fufufu.",
    ],
    "track_offer_full": [
        "📡 <b>{title}</b> sigue en emisión, pero ya vigilo {limit} cosas para ti, {voc}, que es el "
        "máximo. Si quitas alguna en /seguimientos, te hago hueco.",
        "📡 Te vigilaría <b>{title}</b>, {voc}, pero ya tengo {limit} guardias tuyas y Kuro solo tiene "
        "dos ojos. Mira /seguimientos si quieres cambiar alguna.",
    ],
    "track_declined": [
        "👌 Como quieras, {voc}: <b>{title}</b> sin guardia. Si salen más, me lo vuelves a pedir.",
        "👌 Nada de guardia para <b>{title}</b>, {voc}. Kuro se va a su caja de cartón.",
        "👌 Entendido, {voc}. <b>{title}</b>, sin vigilar.",
    ],
    "track_already": [
        "📡 Eso ya está resuelto, {voc}: mira /seguimientos.",
        "📡 Ya me lo habías dicho, {voc}. Lo tienes en /seguimientos.",
    ],
    "track_sent": [
        "📨 Guardia de <b>{title}</b> pedida, {voc}. Si el miauestro dice que sí, vigilaré {when}.",
        "📨 Le paso al miauestro tu petición de vigilar <b>{title}</b> ({when}). Te aviso de lo "
        "que diga, {voc}.",
        "📨 Apuntado en la libreta de guardias: <b>{title}</b>, {when}. Falta el sello del miauestro.",
    ],
    "track_joined": [
        "📡 ¡Hecho, {voc}! <b>{title}</b> ya lo vigilaba para otro cliente, así que te apunto "
        "sin más: {when}.",
        "📡 Suerte, {voc}: ya tenía un ojo puesto en <b>{title}</b> ({when}). Te apunto a la misma guardia.",
    ],
    "track_active": [
        "📡 ¡Guardia montada, {voc}! Vigilo <b>{title}</b> {when}. Cada capítulo nuevo irá al "
        "almacén él solito, y te aviso cuando llegue.",
        "📡 Kuro ya está en el tejado: <b>{title}</b>, {when}. Lo que salga, para dentro, y te lo cuento, nya.",
        "📡 <b>{title}</b> en vigilancia ({when}), {voc}. Ni una paloma se me escapa.",
    ],
    "track_rejected": [
        "❌ El miauestro no quiere vigilar <b>{title}</b>, {voc}. Lo ya pedido sigue en marcha; "
        "lo nuevo, me lo pides cuando salga.",
        "❌ Sin guardia para <b>{title}</b>, {voc}: el miauestro dice que no. Puedes pedirme los "
        "capítulos nuevos a mano cuando salgan.",
    ],
    "track_failed": [
        "⚠️ No he podido montar la guardia de <b>{title}</b>, {voc}. Se me ha enredado el ovillo.",
        "⚠️ La guardia de <b>{title}</b> se ha caído del tejado antes de empezar, {voc}.",
    ],
    "track_ended": [
        "🏁 <b>{title}</b> ha terminado de emitirse, {voc}. Bajo del tejado: ya no lo vigilo.",
        "🏁 Fin de la guardia: <b>{title}</b> ya no está en emisión, {voc}. Kuro vuelve a su caja.",
        "🏁 Se acabó <b>{title}</b>, {voc}. Guardia terminada; si sale otra temporada, me la pides.",
    ],
    "track_stopped": [
        "🗑 Dejo de vigilar <b>{title}</b>, {voc}.",
        "🗑 <b>{title}</b>, sin guardia. Kuro baja del tejado.",
    ],
    "track_stopped_by_boss": [
        "🗑 El miauestro me ha mandado dejar de vigilar <b>{title}</b>, {voc}. Lo ya bajado sigue "
        "en el almacén.",
    ],
    "track_none": [
        "📡 No vigilo nada para ti ahora mismo, {voc}. Cuando pidas algo en emisión, te lo ofrezco.",
        "📡 Ninguna guardia en marcha, {voc}. El tejado está libre.",
    ],
    "track_list_head": [
        "📡 Guardias en marcha ({count}), {voc}:",
        "📡 Lo que vigilo cada semana ({count}):",
    ],
    "track_list_limit": [
        "\nOcupas {count} de {limit} guardias, {voc}. 🗑 para quitar una.",
        "\n{count} de {limit} guardias usadas. Con 🗑 me bajo del tejado.",
    ],
    "track_disabled": [
        "📡 Ahora mismo no puedo hacer guardias, {voc}: la torre de vigilancia está cerrada.",
    ],
    # Se muestra como alerta: texto plano, sin HTML
    "track_gone": [
        "Esa guardia ya no existe, {voc}.",
        "Eso ya no está en mi libreta, {voc}.",
    ],
    "track_admin_request": [
        "📡 {Voc}, <b>{who}</b> quiere que vigile <b>{title}</b> cada semana:",
        "📡 Petición de guardia de <b>{who}</b>, {voc}: <b>{title}</b>.",
    ],
    "track_admin_joined": [
        "📡 <b>{who}</b> se ha apuntado a la guardia de <b>{title}</b>, {voc}. Ya se vigilaba: no gasta nada.",
    ],
    "track_admin_approved": [
        "✅ Guardia montada en change-detection, {voc}.",
        "✅ Hecho, {voc}: <b>{title}</b> vigilado.",
    ],
    "track_admin_rejected": [
        "❌ Sin guardia, {voc}. Se lo digo.",
        "❌ Rechazada, {voc}. Le aviso.",
    ],
    "track_admin_failed": [
        "⚠️ change-detection no ha querido crear la guardia de <b>{title}</b>, {voc}:",
    ],
    "track_admin_ended": [
        "🏁 <b>{title}</b> ya no está en emisión, {voc}: he borrado su guardia.",
    ],
    "track_admin_cd_retired": [
        "📡 {Voc}, he retirado {n} guardia(s) de change-detection: ahora vigilo solo el Drive. Como cambiar "
        "de arma a mitad de temporada, pero con el set ya preparado.",
        "📡 Hecho, {voc}: {n} guardia(s) fuera de change-detection. A partir de ahora, solo el Drive.",
    ],
    "track_admin_delete_failed": [
        "⚠️ No he podido borrar la guardia de <b>{title}</b> en change-detection, {voc}. Quítala a mano:",
    ],
    # Se muestra como alerta: texto plano, sin HTML
    "already_decided": [
        "Esa ya estaba decidida ({status}), {voc}.",
        "Eso ya está resuelto ({status}), {voc}.",
    ],
    # ------------------------------------- Kuro echa de menos al miauestro
    # Un nivel por clave lonely_N (1 = un poco mimoso … el último = despedida);
    # después se calla hasta que vuelva. Hay tantos niveles como claves.
    "lonely_1": [
        "🐈‍⬛ Psst… {voc}. Hace {days} que no pasas por el callejón. Kuro solo lo comenta, ¿eh? Nya.",
        "🐾 {Voc}, he dejado la gatera entreabierta por si vuelves. No es que te eche de menos. Bueno, un poco.",
        "🐈‍⬛ Miau. Nada, solo era para ver si seguías ahí, {voc}. Llevas {days} sin dar señales.",
        "😺 Kuro se ha lamido la pata catorce veces esta tarde, {voc}. Es lo que pasa cuando no vienes.",
        "🐾 {Voc}, el rayo de sol del pasillo ha pasado {days} sin nadie que me viera tumbado en él.",
        "🐈‍⬛ Te he dejado un regalo en la puerta, {voc}. Es un calcetín. Es tuyo. Llevas {days} fuera.",
        "😺 ¿Hola? Kuro aquí. Toc, toc. Con la zarpa, en tu pantalla. {days} sin vernos, {voc}.",
    ],
    "lonely_2": [
        "😿 {Voc}, ya van {days}. He puesto tu cojín al sol, por si acaso. Sigue vacío.",
        "😿 Le he contado a una paloma que tengo un miauestro. No me ha creído, {voc}. Llevas {days} sin aparecer.",
        "🐈‍⬛ {days} sin ti, {voc}. Kuro empieza a sospechar que tienes otro gato. Fsss…",
        "😿 He repasado la libreta de garra tres veces. Tu nombre sigue ahí, {voc}, pero tú no. Nya…",
        "😿 He amasado tu jersey hasta dejarlo en forma de nido, {voc}. {days}. Ahí sigue, esperándote.",
        "🐈‍⬛ La gata Persa del quinto me pregunta por ti, {voc}. Le digo que estás de misión. {days} de misión.",
        "😿 {days}, {voc}. He contado las baldosas del pasillo. Son 48. Y una suelta.",
    ],
    "lonely_3": [
        "😾 {days}, {voc}. {days}. Un felyne no olvida, ¿sabes? Ni perdona fácilmente. Pero vuelve, ¿vale?",
        "🌧️ Ha llovido en el tejado y nadie me ha abierto la ventana. {days} ya, {voc}. Estoy mojado y ofendido.",
        "😿 En Pokke, después de cada cacería, me guardabas un trozo de carne asada. Ahora, {voc}, llevas {days} sin guardarme ni un «hola».",
        "😾 He tirado un vaso de la mesa. Adrede. Mirándote. Aunque no estuvieras, {voc}. {days} sin vernos.",
        "😾 He dormido en tu teclado, {voc}. Llevas {days} fuera, así que ahora es mío. Tecla a tecla.",
        "😾 {days} sin noticias, {voc}. Ni con el Ukanlos tardaste tanto en volver al campamento.",
    ],
    "lonely_4": [
        "🕵️ {Voc}, he abierto una investigación. Pista uno: no estás. Pista dos: llevas {days} sin estar. "
        "Conclusión: Kuro está solo. Caso resuelto. Fsss.",
        "🕵️ He interrogado a las palomas, al Tuerto y a Bigotes, el del puerto. Nadie te ha visto en {days}, {voc}.",
        "🕵️ He puesto carteles en las farolas: «SE BUSCA MIAUESTRO. Responde a "
        "“¿dónde está mi cena?”». {days} sin rastro, {voc}.",
        "🕵️ {days}, {voc}. He seguido tu olor hasta la puerta. Ahí se acaba. Sospechoso, muy sospechoso.",
        "🕵️ Teoría de Kuro: te han abducido. Alternativa: te has ido con un perro. {days} sin ti, "
        "y no sé cuál es peor, {voc}.",
    ],
    "lonely_5": [
        "😭 {Voc}, me he comido el yogur que dejaste en la nevera. Llevaba {days} ahí, igual que tu ausencia. Estaba malo. Como yo.",
        "😭 He empezado a hablar con la aspiradora, {voc}. Ya ves lo desesperado que estoy. {days}.",
        "😭 {days} sin ti, {voc}. He gastado una de mis vidas en echarte de menos. Ya solo me quedan tres. Y bajando.",
        "😭 El bote de pepinillos de la nevera me ha mirado mal, {voc}, y no estabas para protegerme. {days} ya.",
        "😭 He maullado a la luna, a la farola y al microondas, {voc}. Ninguno eras tú. {days}.",
    ],
    "lonely_6": [
        "🍂 {days}, {voc}. Kuro ha aprendido a abrir la nevera solo. No es una amenaza. Es un dato.",
        "🍂 He estado pensando, {voc}. Un gato sin miauestro es solo un gato. Y yo, hace {days}, solo soy un gato.",
        "🍂 He vuelto al callejón donde nos conocimos, {voc}. Los contenedores siguen ahí. Tú no. {days}.",
        "🍂 {days} después, {voc}, he hecho las paces con el silencio. Bueno, casi. Sigo bufándole un poco.",
        "🍂 Los gatos callejeros dicen que me estoy ablandando, {voc}. Que un felyne no espera tanto. {days} esperando.",
    ],
    "lonely_7": [
        "💔 {Voc}… Kuro ha escrito su testamento en la caja de cartón: «todas mis sardinas para el miauestro que me abandonó». "
        "{days}. No te escribo más, que tengo mi orgullo. Pero aquí sigo.",
        "💔 Ya está, {voc}: me he hecho un ovillo y no pienso moverme hasta que vuelvas. Llevo {days}. "
        "Esta es la última vez que te maúllo… hasta que vuelvas.",
        "💔 {days} sin ti, {voc}. He vuelto a mirar viejos tejados, pero ninguno es como el tuyo. "
        "Kuro se calla ya. Sabes dónde encontrarme.",
        "💔 Última carta, {voc}. Tras {days}, Kuro guarda la libreta, apaga la farola y se sienta en la ventana. "
        "Cuando vuelvas, me verás ahí. Siempre.",
    ],
    "lonely_clients": [
        "Por cierto, han pasado {count} encargo(s) mientras no estabas ({who}). Yo los he atendido solito, nya.",
        "Que conste: los clientes sí vienen. {count} encargo(s) estos días ({who}). Tú, no.",
        "Para que lo sepas, han venido a verme ({who}): {count} encargo(s). Ellos sí se acuerdan de Kuro.",
    ],
    "lonely_last_title": [
        "Lo último que me pediste fue <b>{title}</b>. Lo guardo como recuerdo.",
        "Todavía me acuerdo de cuando me pediste <b>{title}</b>. Qué tiempos, nya.",
        "He vuelto a mirar <b>{title}</b>, lo último que me pediste. Duermo encima de su carpeta.",
    ],
    # sin datos: lo que ha hecho Kuro mientras tanto (se mezcla con los dos anteriores)
    "lonely_meanwhile": [
        "Mientras tanto, he ordenado el almacén por colores. Bueno, lo he tirado todo al suelo.",
        "Mientras no estabas he aprendido a encender la tele con la cola. Solo pone la teletienda.",
        "Por si te interesa, he ganado una pelea al gato del vecino. Bueno, empate. Bueno, he huido.",
        "Mientras tanto, he afilado las uñas en tu silla favorita. Por nostalgia.",
        "He estado practicando mi cara de pena en el espejo. Ya me sale sola.",
        "Mientras tanto he contado las palomas del tejado de enfrente. Son once. Ninguna eres tú.",
    ],
    "lonely_back": [
        "😻 ¡{Voc}! ¡Has vuelto! *se frota contra tu pierna* No te había echado de menos ni nada, ¿eh? Nya~",
        "😻 ¡Miauestro! Kuro sabía que volverías. *ronronea a todo volumen*",
        "😸 ¡Por fin, {voc}! Te había guardado el sitio en el sofá. Bueno, lo había usado yo, pero calentito.",
        "😻 ¡Ahí estás, {voc}! *amasa tu regazo con entusiasmo* Ya era hora, nya.",
        "😸 {Voc}, ¡qué bien hueles! A calle y a croquetas. Bienvenido al callejón.",
    ],
    "lonely_back_hurt": [
        "😾 Vaya, vaya… mira quién aparece después de {days}. *se da la vuelta y te enseña la cola* "
        "…Vale, vale, ya se me pasa. ¡Bienvenido, {voc}! 😻",
        "😿➡️😻 {days}, {voc}. Iba a hacerme el ofendido, pero no me sale. ¡Qué alegría verte, nya!",
        "😾 Fsss… ¿Ahora vienes, tras {days}? *te mira fijamente* …Está bien. Pero me debes una lata de sardinas, {voc}.",
        "😾 {days}, {voc}. *finge que duerme* … *abre un ojo* … *ronronea sin querer* ¡Maldita sea! Bienvenido.",
    ],
    # vuelta tras los niveles más dramáticos
    "lonely_back_drama": [
        "😭😻 ¡¡{Voc}!! ¡¡{days}!! *salta a tus brazos, se le olvida el orgullo* No vuelvas a irte tanto, nya…",
        "😻 Has vuelto, {voc}… tras {days}. Kuro rompe el testamento ahora mismo. Bueno, lo rompe a mordiscos.",
        "😭 {days}, {voc}. Gasté una vida esperándote, pero ha merecido la pena. *ronroneo de motor diésel*",
        "😻 ¡El miauestro ha vuelto! *se lo grita a las palomas, al Tuerto y a toda la calle* Tras {days}, {voc}…",
    ],
}

# De madrugada (0-7 h) estas variantes se suman a las normales.
NIGHT_HOURS = range(0, 7)
NIGHT_LINES: dict[str, list[str]] = {
    "help_intro_boss": [
        "🐈‍⬛ ¿Despierto a estas horas, {voc}? Como la noche de la primera Nargacuga: tú afilando la "
        "espada larga y yo de guardia en el campamento.",
        "🐈‍⬛ Hora bruja, {voc}. Kuro tiene las pupilas como platos. ¿Salimos de caza nocturna, como en "
        "las investigaciones de Elgado?",
    ],
    "help_intro_client": [
        "🐈‍⬛ Buenas noches, {voc}. Soy <b>Kuro</b>. En los campamentos del miauestro siempre me tocaba "
        "la guardia de noche, así que a estas horas sigo despierto y con la mochila lista.",
        "🐈‍⬛ ¿Insomnio, {voc}? Normal, hay luna llena. Soy <b>Kuro</b>, felyne retirado de las cacerías "
        "y proveedor de {site} en el turno de noche.",
    ],
    "searching": [
        "🔎 La noche es mi territorio. Rondando {site} en busca de «{query}»…",
        "🔎 Ojos brillando en la oscuridad… Buscando «{query}» por {site}.",
        "🔎 A estas horas {site} está lleno de gatos pardos. Pregunto por «{query}»…",
    ],
    "pick": ["Esto es lo que se mueve de noche por {site}, {voc}. ¿Cuál?"],
    "pick_cards": ["De noche se ve mejor la mercancía, {voc}. ◀️ ▶️ y eliges."],
    "approved": ["👍 ¡Visto bueno para <b>{title}</b>, {voc}! Buena hora para cazar, nya."],
    "approved_boss": ["👍 Cacería nocturna, {voc}: <b>{title}</b>. Mis favoritas."],
    "cancelled": ["Como quieras, {voc}. Sigo mi ronda nocturna por los tejados. 🌙"],
    "admin_no_pending": ["Nada pendiente, {voc}. Me voy a maullarle a la luna. 🌙"],
    "ep_done": ["🌙 <b>{name}</b> {ep:02d}, cazado a la luz de la luna ({n}/{total})."],
    "job_done_all": ["🌙 <b>{name}</b> completo, {voc}: {done} capítulo(s). La noche ha sido buena."],
    "quota_left": ["De madrugada y contando carros, {voc}: te quedan <b>{left}</b> de {limit}."],
}

# Gestos que Kuro añade de vez en cuando al final de algunos mensajes.
ASIDE_CHANCE = 0.18
ASIDES = [
    "se lame una pata",
    "mueve la cola",
    "se atusa los bigotes",
    "ronronea",
    "bosteza enseñando los colmillos",
    "se estira hasta el último pelo",
    "parpadea despacio",
    "afila las uñas en el sofá",
    "olfatea el aire buscando sardinas",
    "se acurruca en la caja de cartón",
    "amasa un cojín",
    "tira un boli de la mesa",
    "persigue su propia cola un momento",
    "se sienta encima del teclado",
    "mira fijamente a una mosca",
    "se rasca la oreja con la pata de atrás",
    "da un cabezazo cariñoso",
    "se tumba panza arriba (es una trampa)",
    "se hace una rosquilla",
    "le bufa a la aspiradora apagada",
    "salta al alféizar",
    "se esconde en una bolsa del súper",
    "mueve las orejas hacia atrás",
    "se lava la cara con mucha dignidad",
]
NIGHT_ASIDES = [
    "los ojos le brillan en la oscuridad",
    "mira la luna",
    "corre por el pasillo sin motivo a las tantas",
    "escucha ruidos que tú no oyes",
]
ASIDE_KEYS = {
    "help_intro_boss", "help_intro_client", "welcome_new", "pick", "pick_cards", "cancelled",
    "approved", "approved_boss", "nothing_new", "job_done_all", "movie_done",
    "quota_left", "quota_admin", "admin_no_pending", "sent_to_admin", "library_complete",
    "lonely_back", "history_mine", "track_active", "track_declined",
}

# ------------------------------------------------ historias de Kuro
# Al final de las claves de STORY_KEYS, de vez en cuando, Kuro cuenta algo
# de su vida. A los clientes, según la confianza (cuántos animes distintos
# se les han bajado: TRUST_STEPS); cuanta más, más hondo (se suman los
# niveles) y más a menudo (LORE_CHANCE). Con quien no ha pedido nada aún,
# nada: solo lo poco que dice al presentarse. Con el miauestro, batallitas.
# Van en cursiva: sin <i> dentro. Solo {voc}/{Voc}/{site} (y {title} en las
# batallitas: algo que se bajó de verdad).
TRUST_STEPS = (1, 3, 7)
LORE_CHANCE = (0.12, 0.2, 0.28)
BATTLE_CHANCE = 0.2
LORE: list[list[str]] = [
    [   # 1: un cliente que ya ha vuelto alguna vez (pinceladas, y presumir del miauestro)
        "Por cierto, {voc}: no siempre viví en este callejón. Antes dormía junto a la chimenea de una "
        "casa en la Aldea Pokke, entre barriles bomba y olor a carne asada.",
        "¿Sabías que fui el felyne del miauestro, {voc}? Yo le pasaba pociones y él tumbaba monstruos "
        "del tamaño de este edificio. Lo de los monstruos se le daba mejor, la verdad.",
        "En el gremio me llamaban «la Sombra», {voc}. Por lo negro, no por lo sigiloso. Lo de sigiloso "
        "vino después, a fuerza de esquivar colas.",
        "Lo de «miauestro» viene de Pokke, {voc}. Le llamaba «maestro» porque no había arma que se le "
        "resistiera, y con mi acento salió así. Le gustó.",
        "Que el miauestro apruebe tu encargo es un honor, {voc}. Ese cazador ha dicho «sí» a cacerías "
        "que hacían temblar a gremios enteros.",
        "En mis tiempos, {voc}, los felynes estábamos rotos: yo aturdía monstruos a porrazos en la cabeza. "
        "Ahora los compañeros son más… decorativos.",
        "Lo de «nya» se me pegó en la cocina felyne de Pokke, {voc}. Allí todos hablábamos así, y ya no "
        "hay quien me lo quite.",
        "El frío no me asusta, {voc}: me crié en las Montañas Nevadas. Sin bebida caliente no se subía "
        "ni a por setas.",
        "Mi primera clienta fue la gata Persa del quinto: un anime de chicas mágicas a cambio de media "
        "sardina. Le sigo guardando cariño.",
        "Tengo siete vidas, {voc}, pero ya no me quedan todas. Algún día te cuento dónde se quedó la primera. "
        "Pista: hacía mucho calor.",
        "Estuve en Moga una temporada, {voc}. Demasiado sol para un gato negro. Yo soy de nieve: de Pokke.",
        "En Kamura hacían el mejor dango del mundo, {voc}. Un canyne llamado Mochi me robaba la mitad. "
        "Todavía no se lo he perdonado.",
        "Si alguna vez oyes una música dramática y caen bombas del cielo, {voc}, no es el fin del mundo: "
        "es un Bazelgeuse. En Astera se colaba en todas las cacerías. En todas.",
        "En Seliana había aguas termales, {voc}. Ahí me bañaba encantado. No es lo mismo que una bañera. "
        "No preguntes por la bañera.",
        "No me ofrezcas pepinillos, {voc}. Es una larga historia con un Deviljho. Otro día.",
    ],
    [   # 2: cliente de confianza (las cacerías y el miauestro en acción)
        "Te lo cuento porque ya eres de la casa, {voc}: el hacha cargada es el arma del miauestro. "
        "Cargaba los viales, escudo en rojo, ¡clac!, a hacha y ¡BUM!: una SAED entera en la cara del "
        "monstruo. Desde que existe esa arma, no la ha soltado.",
        "¿Sabes lo que es una SAED bien metida, {voc}? Al monstruo se le iba media vida de golpe. Los del "
        "grupo gritaban «¡ahí va otra!» y yo ya ni miraba: sabía cómo acababa.",
        "El miauestro tenía un set de hacha cargada para cada elemento, {voc}: fuego, agua, rayo, hielo y "
        "dragón. Y otro para pegar en bruto, con viales de impacto que dejaban al monstruo viendo "
        "pajaritos. Yo le llevaba la cuenta. Con orgullo.",
        "Lo más bonito del miauestro con el hacha cargada era esperar, {voc}. El monstruo atacaba, él "
        "bloqueaba en el momento justo y, antes de que se diera cuenta, le caía la SAED. Castigaba cada "
        "golpe.",
        "Con la ballesta pesada, el miauestro era un muro, {voc}. Escudo acoplado, plantado delante del "
        "monstruo y disparando a quemarropa. Los demás se escondían detrás de él. Yo también.",
        "En Sunbreak, la ballesta pesada del miauestro era una apisonadora, {voc}. Dispersión a quemarropa "
        "y el monstruo se deshacía. Ni el hacha cargada le hacía sombra. Bueno, casi.",
        "Cuando el miauestro tocaba el cuerno de caza, {voc}, el grupo pegaba más fuerte, aguantaba más y "
        "ni oía los rugidos. Y él encajaba golpes que a otro lo habrían mandado al carro.",
        "Con espada y escudo, el miauestro era el ángel del grupo, {voc}: nadie pasaba más de un suspiro "
        "con poca vida ni envenenado. Polvo de vida, antídotos, pociones… y yo ayudando. Nuestro estilo.",
        "En Freedom Unite le corté la cola a un Rathalos plateado, {voc}. Yo solito, con mi arma de "
        "felyne. El miauestro dice que fue su espada larga. Kuro sabe lo que vio.",
        "La primera vida la perdí en el volcán, {voc}: un Akantor, un rugido, la lava… y Kuro volviendo "
        "en el carro, chamuscado y orgulloso. Volvimos al día siguiente y lo tumbamos.",
        "En Astera, {voc}, daba igual lo que fueras a cazar: a mitad de pelea sonaba la música, caían "
        "bombas del cielo y aparecía el Bazelgeuse. El invitado que nadie invitaba. Siempre.",
        "En Bherna los felynes podíamos cazar solos, {voc}: el modo felyne. Mi época de protagonista. El "
        "miauestro me miraba desde el campamento, por fin al revés.",
        "La primera vez que vimos un Valstrax fue en Bherna, {voc}. Algo cayó del cielo como un cometa. El "
        "miauestro sacó el hacha cargada sin pestañear. Yo pestañeé por los dos.",
        "En las cacerías de grupo de Freedom Unite, a los felynes nos dejaban en casa, {voc}. Yo esperaba "
        "en la puerta y, cuando volvían, exigía que me lo contaran todo. Con detalles.",
        "En los Desbocamientos de Kamura, {voc}, el miauestro se plantaba en la puerta con la ballesta "
        "pesada y no pasaba ni el viento. Yo le acercaba la munición. Bueno, la que no me comía.",
        "La primera Nargacuga la cazamos de noche, {voc}. Solo se le veían los ojos rojos. A mí también, "
        "así que durante un rato se hizo un lío.",
        "Bigotes, el del puerto, me enseñó a moverme por {site}. A cambio le guardo las raspas de los "
        "viernes. Un acuerdo de caballeros… y de gatos.",
    ],
    [   # 3: de los de siempre (lo que no cuenta a cualquiera)
        "Ya que eres de los de siempre, {voc}: con el Ukanlos estuvimos a un carro de fallar. Dos del "
        "grupo caídos, el reloj en el último minuto… y el miauestro con el cuerno, aguantando delante "
        "hasta que lo tumbaron. Esa noche nadie durmió en Pokke.",
        "¿Sabes cuántas vidas me quedan, {voc}? Cuatro. Una se quedó en el volcán con el Akantor, otra en "
        "la bañera y otra la noche que saqué al Tuerto de la perrera. Esa no me pesa nada.",
        "Lo de los pepinillos, {voc}: en Astera un Deviljho se coló en la cacería y me agarró con la boca. "
        "Verde, lleno de bultos, babeando… un pepinillo gigante con hambre. El miauestro le metió una SAED "
        "en los morros y me soltó. Desde entonces, nada verde cerca.",
        "El cascabel que llevo me lo puso el miauestro en Pokke, «para no perderte en la ventisca». Hace "
        "años que no suena, {voc}, pero no me lo quito.",
        "Con el Alatreon de Seliana, {voc}, había que pegarle con elemento o te borraba del mapa. Medio "
        "mundo sufrió. El miauestro abrió su set elemental de hacha cargada y fue la llave. Nunca he "
        "estado tan orgulloso de llevarle las pociones.",
        "La trilogía Fatalis, {voc}. El castillo Schrade. Ahí entendí que el miauestro estaba hecho de otra "
        "pasta: cuando todos corrían, él se acercaba con la ballesta pesada.",
        "Y el Fatalis de Iceborne, {voc}, el de verdad. Bloqueo, bloqueo, punto de guardia… y SAED. Una y "
        "otra vez, sin fallar, hasta que el dragón negro cayó. Yo no respiré en toda la cacería.",
        "En Elgado, contra el Malzeno primordial, el grupo cayó dos veces, {voc}. A la tercera el "
        "miauestro sacó la espada y escudo y no dejó caer a nadie más. Desde entonces le llamo «el "
        "curandero», pero solo cuando no me oye.",
        "¿Sabes lo que más admiro del miauestro, {voc}? Que dominaba cuatro armas y además era el mejor "
        "apoyo del grupo. Podía tumbar al monstruo o mantener vivos a todos. Elegía según lo que hiciera "
        "falta. Eso es un cazador.",
        "Llevo una libreta de garra con cada encargo. Tu nombre sale tantas veces, {voc}, que le he "
        "dibujado una estrellita al lado. Antes la usaba para apuntar las hazañas del miauestro. Ocupan "
        "tres libretas.",
        "Cuando el miauestro colgó las armas, {voc}, me vine con él a la ciudad. Me ofrecieron quedarme "
        "de felyne en Elgado, con el Almirante. Les dije que dónde iba a estar mejor que con mi cazador.",
        "La gata Persa del quinto y yo… bueno, {voc}, eso es otra historia. Solo te diré que los martes "
        "compartimos tejado y que no es asunto de las palomas.",
    ],
]
BATTLES = [
    "¿Te acuerdas, {voc}, de la noche que bajamos <b>{title}</b>? Yo me dormí encima del router y aun "
    "así llegó entero. Como el Ukanlos: a un carro de fallar y al final, hecho.",
    "¿Te acuerdas de <b>{title}</b>, {voc}? Esa la cuento en el callejón y cada vez la cacería es más grande.",
    "Como en los viejos tiempos, {voc}: tú eligiendo la presa y yo trayéndola entre los dientes. Igual "
    "que con <b>{title}</b>.",
    "Todavía me acuerdo de cuando llegó <b>{title}</b>, {voc}. Me sentí como al volver de la Ciudadela: "
    "con los bigotes chamuscados y la mochila llena.",
    "<b>{title}</b> llegó sin un solo Bazelgeuse por medio, {voc}. Ni en Astera tuvimos tanta suerte.",
    "¿Te acuerdas de tu primera SAED, {voc}? Fallaste. El monstruo se apartó y la descarga se la llevó "
    "una roca. Desde entonces no has fallado ni una. Yo sí me acuerdo de la roca.",
    "¿Te acuerdas de cuando el grupo empezó a gritar «¡ahí va otra!» cada vez que pasabas a hacha, {voc}? "
    "Yo lo sigo gritando. Por dentro.",
    "¿Te acuerdas de los bloqueos perfectos, {voc}? El monstruo atacaba, tú clavabas el punto de guardia "
    "y le devolvías la SAED. Kuro nunca ha visto nada tan bonito. Y he visto atardeceres en Seliana.",
    "¿Te acuerdas del Alatreon, {voc}? Todo el mundo llorando con el chequeo de elemento y tú sacando el "
    "set de hacha cargada que tocaba. Seis sets, {voc}. Me sigue pareciendo una locura preciosa.",
    "¿Te acuerdas del Fatalis de Iceborne, {voc}? Bloqueo, punto de guardia, SAED. Una y otra vez. Yo "
    "no respiré en toda la cacería.",
    "¿Te acuerdas del Bazelgeuse, {voc}? Ibas a por un Kulu-Ya-Ku y acababas bajo una lluvia de bombas. "
    "Todas las cacerías de rango alto en Astera. Todas.",
    "¿Te acuerdas de aquella vez que el Bazelgeuse llegó justo cuando el monstruo cojeaba, {voc}? Bombas, "
    "carro, y el monstruo se fue a dormir tan tranquilo. Aún le bufo cuando oigo un avión.",
    "¿Te acuerdas del Deviljho que me agarró en Astera, {voc}? Le metiste una SAED en los morros y me "
    "soltó. Te debo una vida. Y desde entonces, nada de pepinillos.",
    "¿Te acuerdas del Akantor del volcán, {voc}? Yo volví en el carro sin una vida y tú, sin cejas. Al "
    "día siguiente lo tumbamos. Nunca me has dado las gracias por el barril.",
    "¿Te acuerdas de cuando le corté la cola al Rathalos plateado, {voc}? Tú dices que fue la espada "
    "larga. Kuro sabe lo que vio.",
    "¿Te acuerdas del Ukanlos, {voc}? Dos del grupo en el suelo, el reloj en el último minuto y tú con el "
    "cuerno, sin caerte. Todavía me tiemblan los bigotes.",
    "¿Te acuerdas de los Desbocamientos de Kamura, {voc}? Tú en la puerta con la ballesta pesada, escudo "
    "delante, y ni un monstruo pasó. Mochi y yo apostábamos cuántos caían por oleada.",
    "¿Te acuerdas de la ballesta pesada en Sunbreak, {voc}? Dispersión a quemarropa y los monstruos se "
    "deshacían. Hubo días en que el hacha cargada se puso celosa.",
    "¿Te acuerdas del Valstrax de Bherna, {voc}? Cayó del cielo como un cometa y tú ni pestañeaste. Yo "
    "estaba en modo felyne, cazando por mi cuenta, y me escondí detrás de ti igual.",
    "¿Te acuerdas de las aguas termales de Seliana, {voc}? Después de cada cacería en la escarcha. Ahí "
    "aprendí que el agua caliente no es el enemigo. La bañera sí.",
    "¿Te acuerdas del Plesioth de la Selva, {voc}? Su golpe de cadera me mandó a la otra punta del mapa. "
    "Tú te reías. Le sigo guardando rencor.",
    "¿Te acuerdas de la primera Nargacuga, {voc}? De noche, sin verle más que los ojos, y tú con la "
    "espada larga esperando el momento. Yo estaba de guardia. Muy valiente. Detrás de una roca.",
    "¿Te acuerdas del Malzeno primordial, {voc}? Dos carros, y a la tercera sacaste la espada y escudo y "
    "no cayó nadie más. El grupo aún te debe esa.",
    "¿Te acuerdas de cuando el Rajang te persiguió por todo el mapa, {voc}? Tú con la ballesta pesada "
    "dándole perdigones a quemarropa y yo aturdiéndolo a porrazos. Qué equipo.",
    "¿Te acuerdas de la ventisca de las Montañas Nevadas, {voc}? Te quedaste sin bebida caliente y te "
    "di la mía. Bueno, me la quitaste. Pero yo te la habría dado.",
    "¿Te acuerdas del castillo Schrade, {voc}? Cuando el Fatalis cayó, el grupo se quedó en silencio un "
    "minuto entero. Yo no: yo maullé. Alguien tenía que celebrarlo.",
    "¿Te acuerdas de Mochi, el canyne de Kamura, {voc}? Me robaba el dango y tú le dabas la razón. Y luego "
    "en Wilds, el Seikret. Siempre hay un bicho que me quiere quitar el sitio.",
    "¿Te acuerdas de cuando el grupo te llamaba «el que no se cae», {voc}? Con el cuerno encajabas todo. "
    "Yo os curaba igual, por si acaso.",
    "Ya lo he dicho alguna vez, {voc}, pero lo repito: de todos los cazadores de Pokke, Astera y Elgado, "
    "Kuro eligió bien. Fufufu.",
    "¿Te acuerdas de la primera vez que nos bloquearon la web, {voc}? Tú buscando atajos y yo bufándole "
    "al router. Al final pasamos por el túnel de la cebolla, como en una misión de recolección clandestina.",
    "Aquella vez que se cayó el servidor a medio capítulo, {voc}… Un Bazelgeuse, seguro. Tú maldiciendo "
    "como cuando te triplecarreaban, y yo tirando cosas de la mesa para animarte.",
]
STORY_KEYS = {
    "approved", "approved_boss", "job_done_all", "movie_done", "cancelled", "quota_left", "quota_admin",
    "admin_no_pending", "library_complete", "sent_to_admin", "nothing_new", "history_mine",
    "track_active", "lonely_back",
}
