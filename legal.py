"""
Madam CEO – information and legal pages (EN / ES / FR).
Fill in the OWNER details below. These texts are a reasonable starting point,
not legal advice: have them reviewed before relying on them.
"""

# ---- Fill these in -----------------------------------------------------------
OWNER_NAME = "Madame CEO"
OWNER_ID = "54022114J"
OWNER_ADDRESS = "Pasaje de la mora 1"
CONTACT_EMAIL = "hello@themadamceo.com"
LAST_UPDATED = "27 October 2026"
# -----------------------------------------------------------------------------

# Each page: slug -> {"title": {lang: str}, "body": {lang: [ (kind, text) ]}}
# kind is "h" (heading) or "p" (paragraph). {email}, {owner}, {id}, {address}, {site}, {updated} are filled in.

PAGES = {
    "about": {
        "title": {"en": "About Madam CEO", "es": "Sobre Madam CEO", "fr": "À propos de Madam CEO"},
        "body": {
            "en": [
                ("p", "Madam CEO is a news site for ambitious women in the corporate world. Every day we select the business stories that matter for your career — leadership, boards, money, workplace policy and deals — and explain why they matter and what you can do about them."),
                ("h", "How we work: our editorial policy"),
                ("p", "Our articles are researched and written with the help of artificial intelligence. For every story, the AI reads several reliable sources, writes an original article in its own words, and lists those sources at the end so you can check them."),
                ("p", "Our rules: we only publish facts confirmed in the sources; we never invent names, figures or quotes; images that are not of the people in the story are labelled as illustrative; and illustrations are marked as created with AI."),
                ("h", "Corrections"),
                ("p", "If you spot a mistake, write to {email} with the link to the article. We review every report and correct or remove inaccurate content as quickly as possible."),
                ("h", "Independence"),
                ("p", "Shops and products mentioned in our Style section are selected independently. If we ever earn a commission from a link, we will say so clearly. Advertising is always labelled as such."),
            ],
            "es": [
                ("p", "Madam CEO es una web de noticias para mujeres con ambición en el mundo corporativo. Cada día seleccionamos las noticias empresariales que importan para tu carrera — liderazgo, consejos, dinero, políticas laborales y operaciones — y explicamos por qué importan y qué puedes hacer."),
                ("h", "Cómo trabajamos: nuestra política editorial"),
                ("p", "Nuestros artículos se investigan y redactan con ayuda de inteligencia artificial. Para cada noticia, la IA consulta varias fuentes fiables, escribe un artículo original con sus propias palabras y cita esas fuentes al final para que puedas comprobarlas."),
                ("p", "Nuestras normas: solo publicamos hechos confirmados en las fuentes; nunca inventamos nombres, cifras ni citas; las imágenes que no muestran a las personas de la noticia se indican como ilustrativas, y las ilustraciones se marcan como creadas con IA."),
                ("h", "Correcciones"),
                ("p", "Si detectas un error, escríbenos a {email} con el enlace al artículo. Revisamos cada aviso y corregimos o retiramos el contenido incorrecto lo antes posible."),
                ("h", "Independencia"),
                ("p", "Las tiendas y productos de nuestra sección de Estilo se seleccionan de forma independiente. Si alguna vez ganamos una comisión por un enlace, lo indicaremos claramente. La publicidad siempre aparece señalada como tal."),
            ],
            "fr": [
                ("p", "Madam CEO est un site d'information pour les femmes ambitieuses du monde de l'entreprise. Chaque jour, nous sélectionnons l'actualité business qui compte pour votre carrière — leadership, conseils d'administration, argent, politiques RH et opérations — et expliquons pourquoi elle compte et ce que vous pouvez faire."),
                ("h", "Notre méthode : la politique éditoriale"),
                ("p", "Nos articles sont recherchés et rédigés avec l'aide de l'intelligence artificielle. Pour chaque sujet, l'IA consulte plusieurs sources fiables, rédige un article original avec ses propres mots et cite ces sources en fin d'article pour que vous puissiez les vérifier."),
                ("p", "Nos règles : nous ne publions que des faits confirmés par les sources ; nous n'inventons jamais de noms, de chiffres ni de citations ; les images qui ne montrent pas les personnes concernées sont indiquées comme illustratives, et les illustrations sont signalées comme créées avec l'IA."),
                ("h", "Corrections"),
                ("p", "Si vous repérez une erreur, écrivez à {email} avec le lien de l'article. Nous examinons chaque signalement et corrigeons ou retirons les contenus inexacts au plus vite."),
                ("h", "Indépendance"),
                ("p", "Les boutiques et produits cités dans notre rubrique Style sont choisis en toute indépendance. Si nous touchons un jour une commission sur un lien, nous l'indiquerons clairement. La publicité est toujours signalée comme telle."),
            ],
        },
    },
    "contact": {
        "title": {"en": "Contact", "es": "Contacto", "fr": "Contact"},
        "body": {
            "en": [("p", "Questions, corrections, partnerships or press: write to {email}. We usually reply within a few working days.")],
            "es": [("p", "Preguntas, correcciones, colaboraciones o prensa: escríbenos a {email}. Solemos responder en pocos días laborables.")],
            "fr": [("p", "Questions, corrections, partenariats ou presse : écrivez à {email}. Nous répondons généralement sous quelques jours ouvrés.")],
        },
    },
    "advertise": {
        "title": {"en": "Advertise with us", "es": "Anúnciate con nosotros", "fr": "Annoncez chez nous"},
        "body": {
            "en": [
                ("p", "Madam CEO reaches ambitious professional women in English, Spanish and French: managers, directors, executives and founders who care about their careers, money and style."),
                ("h", "Formats"),
                ("p", "Display banners on the homepage and articles, sponsored placements in our Style section, and sponsorship of the Weekly Brief newsletter. All advertising is clearly labelled."),
                ("p", "Write to {email} for our audience figures and rates."),
            ],
            "es": [
                ("p", "Madam CEO llega a mujeres profesionales con ambición en inglés, español y francés: mandos intermedios, directivas y fundadoras a las que les importa su carrera, su dinero y su estilo."),
                ("h", "Formatos"),
                ("p", "Banners en la portada y en los artículos, espacios patrocinados en la sección de Estilo y patrocinio de la newsletter semanal. Toda la publicidad aparece claramente señalada."),
                ("p", "Escríbenos a {email} para conocer nuestras cifras de audiencia y tarifas."),
            ],
            "fr": [
                ("p", "Madam CEO touche des femmes actives et ambitieuses en anglais, espagnol et français : managers, directrices, dirigeantes et fondatrices attentives à leur carrière, leur argent et leur style."),
                ("h", "Formats"),
                ("p", "Bannières sur la page d'accueil et les articles, emplacements sponsorisés dans la rubrique Style et sponsoring de la newsletter hebdomadaire. Toute publicité est clairement signalée."),
                ("p", "Écrivez à {email} pour connaître notre audience et nos tarifs."),
            ],
        },
    },
    "privacy": {
        "title": {"en": "Privacy policy", "es": "Política de privacidad", "fr": "Politique de confidentialité"},
        "body": {
            "en": [
                ("p", "Last updated: {updated}."),
                ("h", "Who is responsible"),
                ("p", "The controller of your personal data is {owner} ({id}), {address}. Contact: {email}."),
                ("h", "What data we process and why"),
                ("p", "Browsing: our hosting provider processes technical data such as your IP address to deliver the site securely (legitimate interest). Advertising: with your consent, Google and its partners may use cookies and similar technologies to show and measure ads, including personalised ads (consent). Newsletter: if you subscribe, our email provider processes your email address to send it to you (consent); you can unsubscribe at any time from any email. Contact: if you write to us, we use your message only to reply (legitimate interest)."),
                ("h", "Who receives data"),
                ("p", "Service providers that help us run the site, such as our hosting provider (GitHub), our domain and DNS provider (Cloudflare), Google (advertising) and our newsletter provider. Some are located outside the European Economic Area and rely on appropriate safeguards such as the European Commission's standard contractual clauses or adequacy decisions."),
                ("h", "How long we keep it"),
                ("p", "Only as long as needed for each purpose: newsletter data until you unsubscribe; messages for as long as needed to handle your request; advertising cookies according to the settings in our consent tool."),
                ("h", "Your rights"),
                ("p", "You can access, rectify or erase your data, object to or restrict its processing, request portability and withdraw consent at any time by writing to {email}. You can also complain to your data protection authority (in Spain, the Agencia Española de Protección de Datos, aepd.es)."),
                ("p", "Language preferences and game progress are stored only in your own browser and are never sent to us."),
            ],
            "es": [
                ("p", "Última actualización: {updated}."),
                ("h", "Responsable"),
                ("p", "El responsable del tratamiento de tus datos es {owner} ({id}), {address}. Contacto: {email}."),
                ("h", "Qué datos tratamos y para qué"),
                ("p", "Navegación: nuestro proveedor de alojamiento trata datos técnicos como tu dirección IP para servir la web de forma segura (interés legítimo). Publicidad: con tu consentimiento, Google y sus socios pueden usar cookies y tecnologías similares para mostrar y medir anuncios, incluidos anuncios personalizados (consentimiento). Newsletter: si te suscribes, nuestro proveedor de email trata tu dirección para enviártela (consentimiento); puedes darte de baja en cualquier momento desde cualquier envío. Contacto: si nos escribes, usamos tu mensaje solo para responderte (interés legítimo)."),
                ("h", "A quién se comunican"),
                ("p", "A proveedores que nos ayudan a gestionar la web, como el alojamiento (GitHub), el dominio y DNS (Cloudflare), Google (publicidad) y el proveedor de la newsletter. Algunos están fuera del Espacio Económico Europeo y se amparan en garantías adecuadas, como las cláusulas contractuales tipo de la Comisión Europea o decisiones de adecuación."),
                ("h", "Cuánto tiempo los conservamos"),
                ("p", "Solo el necesario para cada finalidad: los datos de la newsletter hasta que te des de baja; los mensajes, el tiempo necesario para atender tu solicitud; las cookies publicitarias, según la configuración de nuestra herramienta de consentimiento."),
                ("h", "Tus derechos"),
                ("p", "Puedes acceder, rectificar o suprimir tus datos, oponerte o limitar su tratamiento, solicitar la portabilidad y retirar tu consentimiento en cualquier momento escribiendo a {email}. También puedes reclamar ante la Agencia Española de Protección de Datos (aepd.es)."),
                ("p", "Tus preferencias de idioma y tu progreso en el juego se guardan solo en tu navegador y nunca se nos envían."),
            ],
            "fr": [
                ("p", "Dernière mise à jour : {updated}."),
                ("h", "Responsable du traitement"),
                ("p", "Le responsable du traitement de vos données est {owner} ({id}), {address}. Contact : {email}."),
                ("h", "Données traitées et finalités"),
                ("p", "Navigation : notre hébergeur traite des données techniques comme votre adresse IP pour fournir le site de manière sécurisée (intérêt légitime). Publicité : avec votre consentement, Google et ses partenaires peuvent utiliser des cookies et technologies similaires pour afficher et mesurer des annonces, y compris personnalisées (consentement). Newsletter : si vous vous abonnez, notre prestataire d'emailing traite votre adresse pour vous l'envoyer (consentement) ; vous pouvez vous désabonner à tout moment. Contact : si vous nous écrivez, votre message sert uniquement à vous répondre (intérêt légitime)."),
                ("h", "Destinataires"),
                ("p", "Les prestataires qui nous aident à faire fonctionner le site : hébergement (GitHub), domaine et DNS (Cloudflare), Google (publicité) et notre prestataire de newsletter. Certains sont situés hors de l'Espace économique européen et s'appuient sur des garanties appropriées, comme les clauses contractuelles types de la Commission européenne ou des décisions d'adéquation."),
                ("h", "Durée de conservation"),
                ("p", "Uniquement le temps nécessaire : données newsletter jusqu'au désabonnement ; messages le temps de traiter votre demande ; cookies publicitaires selon les paramètres de notre outil de consentement."),
                ("h", "Vos droits"),
                ("p", "Vous pouvez accéder à vos données, les rectifier ou les effacer, vous opposer à leur traitement ou le limiter, demander leur portabilité et retirer votre consentement à tout moment en écrivant à {email}. Vous pouvez aussi saisir votre autorité de protection des données (en France, la CNIL ; en Espagne, l'AEPD)."),
                ("p", "Vos préférences de langue et votre progression dans le jeu sont stockées uniquement dans votre navigateur et ne nous sont jamais transmises."),
            ],
        },
    },
    "cookies": {
        "title": {"en": "Cookie policy", "es": "Política de cookies", "fr": "Politique de cookies"},
        "body": {
            "en": [
                ("p", "Last updated: {updated}."),
                ("p", "Cookies are small files stored in your browser. We use them only for the purposes below."),
                ("h", "Necessary storage"),
                ("p", "Your language choice and Power Word progress are saved in your browser's local storage so the site works as you expect. They are never sent to us and need no consent."),
                ("h", "Advertising cookies (only with your consent)"),
                ("p", "Google and its advertising partners may set cookies to show ads, limit how often you see them, measure their performance and, if you agree, personalise them. You choose in the consent message shown on your first visit, and you can change your choice at any time with the 'Privacy settings' link at the bottom of every page."),
                ("p", "You can also block or delete cookies in your browser settings. Learn how Google uses data at policies.google.com/technologies/partner-sites."),
            ],
            "es": [
                ("p", "Última actualización: {updated}."),
                ("p", "Las cookies son pequeños archivos que se guardan en tu navegador. Solo las usamos para lo siguiente."),
                ("h", "Almacenamiento necesario"),
                ("p", "Tu idioma y tu progreso en Power Word se guardan en el almacenamiento local de tu navegador para que la web funcione como esperas. Nunca se nos envían y no requieren consentimiento."),
                ("h", "Cookies publicitarias (solo con tu consentimiento)"),
                ("p", "Google y sus socios publicitarios pueden instalar cookies para mostrar anuncios, limitar cuántas veces los ves, medir su rendimiento y, si lo aceptas, personalizarlos. Lo decides en el aviso de consentimiento de tu primera visita y puedes cambiarlo cuando quieras con el enlace 'Configuración de privacidad' al pie de cada página."),
                ("p", "También puedes bloquear o borrar las cookies desde tu navegador. Más información sobre cómo usa Google los datos en policies.google.com/technologies/partner-sites."),
            ],
            "fr": [
                ("p", "Dernière mise à jour : {updated}."),
                ("p", "Les cookies sont de petits fichiers enregistrés dans votre navigateur. Nous ne les utilisons que pour les finalités ci-dessous."),
                ("h", "Stockage nécessaire"),
                ("p", "Votre choix de langue et votre progression à Power Word sont enregistrés dans le stockage local de votre navigateur pour que le site fonctionne correctement. Ils ne nous sont jamais transmis et ne nécessitent pas de consentement."),
                ("h", "Cookies publicitaires (uniquement avec votre consentement)"),
                ("p", "Google et ses partenaires publicitaires peuvent déposer des cookies pour afficher des annonces, limiter leur répétition, mesurer leurs performances et, si vous l'acceptez, les personnaliser. Vous choisissez dans le message de consentement affiché lors de votre première visite et pouvez modifier votre choix à tout moment via le lien « Paramètres de confidentialité » en bas de chaque page."),
                ("p", "Vous pouvez aussi bloquer ou supprimer les cookies dans votre navigateur. Pour savoir comment Google utilise les données : policies.google.com/technologies/partner-sites."),
            ],
        },
    },
    "legal": {
        "title": {"en": "Legal notice", "es": "Aviso legal", "fr": "Mentions légales"},
        "body": {
            "en": [
                ("p", "In accordance with Spanish Law 34/2002 on Information Society Services (LSSI): this website, {site}, is owned by {owner}, tax ID {id}, address {address}, email {email}."),
                ("h", "Use of the site"),
                ("p", "Content is provided for information only and does not constitute financial, legal or career advice. Although we take care to check our sources, we cannot guarantee that all information is complete or up to date. Links to third-party sites are provided for convenience; we are not responsible for their content."),
                ("h", "Intellectual property"),
                ("p", "Texts and illustrations are owned by {owner} unless stated otherwise. Photographs belong to their authors and are used under the licence of the platform credited with each image."),
            ],
            "es": [
                ("p", "En cumplimiento de la Ley 34/2002 de Servicios de la Sociedad de la Información (LSSI): esta web, {site}, es titularidad de {owner}, NIF {id}, con domicilio en {address} y email {email}."),
                ("h", "Uso de la web"),
                ("p", "Los contenidos tienen carácter informativo y no constituyen asesoramiento financiero, legal ni profesional. Aunque revisamos nuestras fuentes, no podemos garantizar que toda la información sea completa o esté actualizada. Los enlaces a webs de terceros se ofrecen por comodidad; no somos responsables de su contenido."),
                ("h", "Propiedad intelectual"),
                ("p", "Los textos e ilustraciones pertenecen a {owner} salvo que se indique lo contrario. Las fotografías pertenecen a sus autores y se usan bajo la licencia de la plataforma indicada en cada imagen."),
            ],
            "fr": [
                ("p", "Conformément à la loi espagnole 34/2002 sur les services de la société de l'information (LSSI) : ce site, {site}, est édité par {owner}, identifiant fiscal {id}, adresse {address}, email {email}."),
                ("h", "Utilisation du site"),
                ("p", "Les contenus sont fournis à titre d'information et ne constituent pas un conseil financier, juridique ou professionnel. Bien que nous vérifiions nos sources, nous ne pouvons garantir que toutes les informations sont complètes ou à jour. Les liens vers des sites tiers sont fournis par commodité ; nous ne sommes pas responsables de leur contenu."),
                ("h", "Propriété intellectuelle"),
                ("p", "Les textes et illustrations appartiennent à {owner} sauf mention contraire. Les photographies appartiennent à leurs auteurs et sont utilisées selon la licence de la plateforme créditée sous chaque image."),
            ],
        },
    },
}

FOOTER_ORDER = ["about", "contact", "advertise", "privacy", "cookies", "legal"]
