"""
Power Word – Madam CEO's daily word game.
Guess the five-letter business word of the day in six tries.
The word list, styles and game logic live here; ascent_news.py builds the page.
"""

# word, then a short definition in English, Spanish and French
WORDS = [
    ("BOARD", "The group of directors that oversees a company and its leadership.",
     "Consejo de administración: el grupo que supervisa una empresa y a su dirección.",
     "Conseil d'administration : le groupe qui supervise l'entreprise et sa direction."),
    ("PITCH", "A short, persuasive presentation of an idea to investors or clients.",
     "Presentación breve y persuasiva de una idea ante inversores o clientes.",
     "Présentation courte et convaincante d'une idée à des investisseurs ou clients."),
    ("YIELD", "The income an investment returns, usually as a percentage.",
     "Rentabilidad: lo que genera una inversión, normalmente en porcentaje.",
     "Rendement : ce que rapporte un investissement, souvent en pourcentage."),
    ("ASSET", "Anything of value a company or person owns.",
     "Activo: cualquier cosa de valor que posee una empresa o persona.",
     "Actif : tout ce qui a de la valeur et appartient à une entreprise ou une personne."),
    ("AUDIT", "An independent check of a company's accounts or processes.",
     "Auditoría: revisión independiente de las cuentas o procesos de una empresa.",
     "Audit : vérification indépendante des comptes ou des processus d'une entreprise."),
    ("BONUS", "Extra pay on top of salary, often tied to performance.",
     "Pago extra además del salario, a menudo ligado al rendimiento.",
     "Prime : rémunération en plus du salaire, souvent liée à la performance."),
    ("BRAND", "The identity and reputation that people associate with a company or a person.",
     "Marca: la identidad y reputación que se asocia a una empresa o persona.",
     "Marque : l'identité et la réputation associées à une entreprise ou une personne."),
    ("CHAIR", "The person who leads a board or a meeting.",
     "Presidenta: la persona que dirige un consejo o una reunión.",
     "Présidente : la personne qui dirige un conseil ou une réunion."),
    ("STAKE", "A share of ownership in a company.",
     "Participación: una parte de la propiedad de una empresa.",
     "Participation : une part de propriété dans une entreprise."),
    ("COACH", "Someone who helps you develop skills and reach your goals.",
     "Persona que te ayuda a desarrollar habilidades y alcanzar tus objetivos.",
     "Personne qui vous aide à développer vos compétences et atteindre vos objectifs."),
    ("MERGE", "To combine two companies into one.",
     "Fusionar: unir dos empresas en una sola.",
     "Fusionner : réunir deux entreprises en une seule."),
    ("QUOTA", "A target you are expected to reach, such as a sales goal.",
     "Cuota: un objetivo que se espera que alcances, como una meta de ventas.",
     "Quota : un objectif à atteindre, comme un objectif de ventes."),
    ("RAISE", "An increase in salary, or money collected from investors.",
     "Subida de sueldo, o dinero captado de inversores en una ronda.",
     "Augmentation de salaire, ou fonds levés auprès d'investisseurs."),
    ("SHARE", "A unit of ownership in a company.",
     "Acción: una unidad de propiedad de una empresa.",
     "Action : une unité de propriété dans une entreprise."),
    ("STOCK", "Shares of a company traded on the market.",
     "Acciones de una empresa que se negocian en bolsa.",
     "Actions d'une entreprise échangées en bourse."),
    ("VALUE", "What something is worth, or the benefit it brings.",
     "Valor: lo que algo vale, o el beneficio que aporta.",
     "Valeur : ce que vaut une chose, ou le bénéfice qu'elle apporte."),
    ("HEDGE", "An investment made to reduce the risk of another.",
     "Cobertura: inversión que reduce el riesgo de otra.",
     "Couverture : placement qui réduit le risque d'un autre."),
    ("INDEX", "A measure that tracks a group of stocks, like the S&P 500.",
     "Índice: indicador que sigue a un grupo de acciones, como el IBEX 35.",
     "Indice : indicateur qui suit un groupe d'actions, comme le CAC 40."),
    ("LEASE", "A contract to rent property or equipment for a set time.",
     "Arrendamiento: contrato para alquilar un bien durante un tiempo.",
     "Bail : contrat de location d'un bien pour une durée donnée."),
    ("OFFER", "A job proposal with salary and terms.",
     "Oferta: una propuesta de trabajo con salario y condiciones.",
     "Offre : une proposition d'emploi avec salaire et conditions."),
    ("OWNER", "The person who holds the rights to a business or asset.",
     "Propietaria: quien tiene los derechos sobre un negocio o bien.",
     "Propriétaire : la personne qui détient une entreprise ou un bien."),
    ("PANEL", "A group of experts who discuss a topic in public.",
     "Mesa redonda: grupo de expertas que debaten un tema en público.",
     "Table ronde : groupe d'expertes qui débattent d'un sujet en public."),
    ("PRICE", "The amount asked for a product, service or share.",
     "Precio: lo que se pide por un producto, servicio o acción.",
     "Prix : le montant demandé pour un produit, un service ou une action."),
    ("PROXY", "A person authorised to vote on behalf of a shareholder.",
     "Persona autorizada a votar en nombre de una accionista.",
     "Mandataire : personne autorisée à voter au nom d'une actionnaire."),
    ("RALLY", "A strong rise in market prices after a fall.",
     "Fuerte subida de los mercados tras una caída.",
     "Forte remontée des marchés après une baisse."),
    ("RATIO", "A comparison between two figures, like debt to equity.",
     "Ratio: comparación entre dos cifras, como deuda sobre patrimonio.",
     "Ratio : comparaison entre deux chiffres, comme dette sur fonds propres."),
    ("SCALE", "To grow a business quickly without costs growing as fast.",
     "Escalar: hacer crecer un negocio rápido sin que los costes crezcan igual.",
     "Passer à l'échelle : croître vite sans que les coûts suivent au même rythme."),
    ("SKILL", "An ability you can learn, practise and show.",
     "Habilidad: una capacidad que puedes aprender, practicar y demostrar.",
     "Compétence : une capacité que l'on peut apprendre, pratiquer et montrer."),
    ("SPEND", "The money a company or person pays out.",
     "Gasto: el dinero que desembolsa una empresa o persona.",
     "Dépenses : l'argent qu'une entreprise ou une personne débourse."),
    ("STAFF", "The people who work for an organisation.",
     "Plantilla: las personas que trabajan en una organización.",
     "Personnel : les personnes qui travaillent pour une organisation."),
    ("TERMS", "The conditions of a deal or contract.",
     "Condiciones de un acuerdo o contrato.",
     "Conditions d'un accord ou d'un contrat."),
    ("TRADE", "To buy and sell goods, services or securities.",
     "Comerciar: comprar y vender bienes, servicios o valores.",
     "Échanger : acheter et vendre des biens, des services ou des titres."),
    ("TREND", "The general direction in which something is moving.",
     "Tendencia: la dirección general en la que algo evoluciona.",
     "Tendance : la direction générale dans laquelle quelque chose évolue."),
    ("VOICE", "Your ability to be heard and influence decisions.",
     "Voz: tu capacidad de hacerte oír e influir en las decisiones.",
     "Voix : votre capacité à être entendue et à peser sur les décisions."),
    ("AGENT", "Someone who acts or negotiates on another person's behalf.",
     "Agente: quien actúa o negocia en nombre de otra persona.",
     "Agent : personne qui agit ou négocie pour le compte d'une autre."),
    ("ALPHA", "Return above what the market delivers.",
     "Rentabilidad por encima de la que da el mercado.",
     "Rendement supérieur à celui du marché."),
    ("CHART", "A graph that shows data visually.",
     "Gráfico: representación visual de datos.",
     "Graphique : représentation visuelle de données."),
    ("CYCLE", "A repeated pattern, like the economic or budget cycle.",
     "Ciclo: un patrón que se repite, como el ciclo económico.",
     "Cycle : un schéma qui se répète, comme le cycle économique."),
    ("DRAFT", "A first version of a document or contract.",
     "Borrador: primera versión de un documento o contrato.",
     "Brouillon : première version d'un document ou d'un contrat."),
    ("ETHIC", "A principle that guides how you behave at work.",
     "Ética: un principio que guía tu forma de actuar en el trabajo.",
     "Éthique : un principe qui guide votre conduite au travail."),
    ("FOCUS", "Concentrating your time and energy on what matters most.",
     "Enfoque: concentrar tiempo y energía en lo más importante.",
     "Concentration : consacrer son temps et son énergie à l'essentiel."),
    ("FORUM", "A meeting or platform for open discussion.",
     "Foro: reunión o espacio para el debate abierto.",
     "Forum : réunion ou espace de discussion ouverte."),
    ("FRAME", "To present an issue in a way that shapes how others see it.",
     "Enmarcar: presentar un tema de forma que influya en cómo lo ven otros.",
     "Cadrer : présenter un sujet de façon à orienter la perception des autres."),
    ("GRANT", "Money given for a project that does not need to be repaid.",
     "Subvención: dinero para un proyecto que no hay que devolver.",
     "Subvention : argent accordé pour un projet, sans remboursement."),
    ("GUIDE", "To lead or advise others on the way forward.",
     "Guiar: orientar o aconsejar a otros sobre el camino a seguir.",
     "Guider : orienter ou conseiller les autres sur la voie à suivre."),
    ("INPUT", "Ideas or information you contribute to a decision.",
     "Aportación: ideas o información que contribuyes a una decisión.",
     "Contribution : idées ou informations apportées à une décision."),
    ("LEGAL", "Related to the law, or the team that handles it.",
     "Relativo a la ley, o el equipo jurídico que se ocupa de ello.",
     "Relatif au droit, ou l'équipe juridique qui s'en occupe."),
    ("MEDIA", "Newspapers, TV and online outlets that share news.",
     "Medios: prensa, televisión y webs que difunden noticias.",
     "Médias : presse, télévision et sites qui diffusent l'information."),
    ("MERIT", "Being rewarded for the quality of your work.",
     "Mérito: ser recompensada por la calidad de tu trabajo.",
     "Mérite : être récompensée pour la qualité de son travail."),
    ("MODEL", "A plan for how a business makes money, or a financial forecast.",
     "Modelo: cómo gana dinero un negocio, o una previsión financiera.",
     "Modèle : comment une entreprise gagne de l'argent, ou une prévision financière."),
    ("NICHE", "A small, specialised part of a market.",
     "Nicho: una parte pequeña y especializada de un mercado.",
     "Niche : une petite partie spécialisée d'un marché."),
    ("ORDER", "A request from a customer to buy something.",
     "Pedido: solicitud de compra de un cliente.",
     "Commande : demande d'achat d'un client."),
    ("PEERS", "Colleagues at the same level as you.",
     "Colegas de tu mismo nivel.",
     "Pairs : collègues du même niveau que vous."),
    ("PILOT", "A small trial run before a full launch.",
     "Piloto: prueba a pequeña escala antes del lanzamiento.",
     "Pilote : essai à petite échelle avant un lancement complet."),
    ("POWER", "The ability to influence people and outcomes.",
     "Poder: la capacidad de influir en personas y resultados.",
     "Pouvoir : la capacité d'influencer les personnes et les résultats."),
    ("QUERY", "A question that asks for information or clarification.",
     "Consulta: pregunta que pide información o aclaración.",
     "Requête : question qui demande une information ou une précision."),
    ("RIVAL", "A competitor in the same market.",
     "Rival: un competidor en el mismo mercado.",
     "Rival : un concurrent sur le même marché."),
    ("ROUND", "A stage of fundraising, such as a Series A.",
     "Ronda: una fase de financiación, como una Serie A.",
     "Tour de table : une étape de levée de fonds, comme une Série A."),
    ("SALES", "The team and activity of selling a company's products.",
     "Ventas: el equipo y la actividad de vender los productos.",
     "Ventes : l'équipe et l'activité de vente des produits."),
    ("SLIDE", "One page of a presentation deck.",
     "Diapositiva: una página de una presentación.",
     "Diapositive : une page d'une présentation."),
    ("STAGE", "A platform to speak in public, or a phase of growth.",
     "Escenario para hablar en público, o una fase de crecimiento.",
     "Scène pour prendre la parole, ou une phase de croissance."),
    ("STEER", "To guide the direction of a team or project.",
     "Dirigir el rumbo de un equipo o proyecto.",
     "Piloter : orienter la direction d'une équipe ou d'un projet."),
    ("STYLE", "Your personal way of leading, working or dressing.",
     "Estilo: tu forma personal de liderar, trabajar o vestir.",
     "Style : votre façon personnelle de diriger, travailler ou vous habiller."),
    ("SUITE", "The top executives as a group, as in the C-suite.",
     "La cúpula directiva en conjunto, como en el C-suite.",
     "L'ensemble des dirigeants, comme dans la C-suite."),
    ("TABLE", "A seat at the table means a place where decisions are made.",
     "Mesa: tener un sitio en la mesa es estar donde se decide.",
     "Table : avoir une place à la table, c'est être là où l'on décide."),
    ("TITLE", "The name of your role, like Director or Vice President.",
     "Cargo: el nombre de tu puesto, como Directora o Vicepresidenta.",
     "Titre : le nom de votre poste, comme Directrice ou Vice-présidente."),
    ("TOKEN", "A digital unit of value, or a small symbolic gesture.",
     "Unidad digital de valor, o un gesto simbólico.",
     "Jeton : unité numérique de valeur, ou geste symbolique."),
    ("TRUST", "Confidence that others will act reliably and fairly.",
     "Confianza en que otros actuarán de forma fiable y justa.",
     "Confiance : certitude que les autres agiront de façon fiable et juste."),
    ("UNION", "An organisation that represents workers' interests.",
     "Sindicato: organización que representa a los trabajadores.",
     "Syndicat : organisation qui représente les salariés."),
    ("VENUE", "The place where an event or meeting happens.",
     "Lugar donde se celebra un evento o reunión.",
     "Lieu où se déroule un événement ou une réunion."),
    ("WAGES", "Pay earned for work, usually by the hour or week.",
     "Salarios: la paga por el trabajo, normalmente por horas o semanas.",
     "Salaires : rémunération du travail, souvent à l'heure ou à la semaine."),
    ("WORTH", "The value of something, or your own value at work.",
     "Valía: el valor de algo, o el tuyo propio en el trabajo.",
     "Valeur : ce que vaut une chose, ou votre propre valeur au travail."),
    ("CLOSE", "To finalise a deal or a sale.",
     "Cerrar: concretar un acuerdo o una venta.",
     "Conclure : finaliser un accord ou une vente."),
    ("DEBIT", "Money taken out of an account.",
     "Cargo: dinero que sale de una cuenta.",
     "Débit : argent retiré d'un compte."),
    ("FUNDS", "Money set aside or raised for a purpose.",
     "Fondos: dinero reservado o captado para un fin.",
     "Fonds : argent réservé ou levé pour un objectif."),
    ("LEVEL", "Your seniority in an organisation.",
     "Nivel: tu grado de responsabilidad en una organización.",
     "Niveau : votre degré de responsabilité dans une organisation."),
    ("MONEY", "What you negotiate, earn, save and invest.",
     "Dinero: lo que negocias, ganas, ahorras e inviertes.",
     "Argent : ce que vous négociez, gagnez, épargnez et investissez."),
]

GAME_CSS = """
.game { max-width:520px; margin:0 auto; padding:36px 16px 64px; text-align:center; }
.game h1 { font-family:var(--serif); font-weight:600; font-size:clamp(40px, 7vw, 56px); color:var(--granate); margin:0; }
.game .game-sub { color:var(--muted); margin:6px 0 4px; }
.game .game-num { font-size:12px; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:var(--accent); margin:0 0 24px; }
.board { display:grid; grid-template-rows:repeat(6, 1fr); gap:6px; width:min(330px, 100%); margin:0 auto 20px; }
.row { display:grid; grid-template-columns:repeat(5, 1fr); gap:6px; }
.tile { aspect-ratio:1; display:flex; align-items:center; justify-content:center; border:2px solid #D9BFC3; background:#FFF8F7;
  font-family:var(--sans); font-weight:700; font-size:clamp(22px, 6vw, 30px); color:var(--ink); border-radius:4px; text-transform:uppercase; }
.tile.filled { border-color:#8A6A70; }
.tile.hit { background:var(--granate); border-color:var(--granate); color:#fff; }
.tile.near { background:var(--gold); border-color:var(--gold); color:var(--ink); }
.tile.miss { background:#8C8A90; border-color:#8C8A90; color:#fff; }
.row.shake { animation:shake .35s; }
@keyframes shake { 0%,100% { transform:translateX(0) } 25% { transform:translateX(-6px) } 75% { transform:translateX(6px) } }
.keys { display:flex; flex-direction:column; gap:7px; width:100%; max-width:500px; margin:0 auto; }
.keyrow { display:flex; gap:5px; justify-content:center; }
.key { flex:1 1 0; min-width:0; height:54px; border:0; border-radius:6px; background:#E8D3D1; color:var(--ink); font:inherit;
  font-weight:700; font-size:14px; cursor:pointer; text-transform:uppercase; }
.key.wide { flex:1.6 1 0; font-size:12px; }
.key.hit { background:var(--granate); color:#fff; }
.key.near { background:var(--gold); }
.key.miss { background:#8C8A90; color:#fff; }
.game-msg { min-height:28px; font-weight:600; color:var(--granate); margin:0 0 12px; }
.reveal { display:none; margin:24px auto 0; padding:24px; background:#fff; border-radius:6px; text-align:left; border-top:4px solid var(--granate); }
.reveal.show { display:block; }
.reveal h2 { margin:0 0 8px; font-family:var(--serif); font-size:30px; color:var(--granate); letter-spacing:.06em; }
.reveal p { margin:0 0 12px; }
.stats { display:flex; gap:20px; margin:12px 0 16px; }
.stats div { display:flex; flex-direction:column; }
.stats b { font-size:26px; font-family:var(--serif); color:var(--granate); }
.stats span { font-size:12px; color:var(--muted); }
.share { display:inline-flex; gap:8px; align-items:center; min-height:48px; padding:0 22px; border-radius:999px; border:0;
  background:var(--granate); color:#fff; font:inherit; font-weight:600; cursor:pointer; }
.share:hover { background:var(--ink); }
.how { margin:28px auto 0; text-align:left; font-size:14px; color:var(--muted); }
.how summary { cursor:pointer; font-weight:600; color:var(--ink); }
.legend { display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; }
.legend span { display:inline-flex; align-items:center; gap:6px; }
.legend i { width:18px; height:18px; border-radius:3px; display:inline-block; }
"""

GAME_JS = """
(function () {
  var data = window.POWER_WORDS, siteUrl = window.SITE_URL || location.origin;
  var start = Date.UTC(2026, 9, 27);
  var now = new Date();
  var today = Math.floor((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - start) / 86400000);
  var num = Math.max(0, today) + 1;
  var entry = data[Math.max(0, today) % data.length];
  var answer = entry[0];
  var MAX = 6, rows = [], current = '', done = false;
  var board = document.getElementById('board'), msg = document.getElementById('msg');
  var key = 'pw-' + num;
  document.querySelectorAll('.pw-num').forEach(function (e) { e.textContent = num; });

  function load(k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  function lang() { return document.body.dataset.lang || 'en'; }
  function t(o) { return o[lang()] || o.en; }
  var TXT = {
    short: { en: 'Five letters, please', es: 'Tienen que ser cinco letras', fr: 'Il faut cinq lettres' },
    win: { en: 'Brilliant — you got it!', es: '¡Brillante, la has acertado!', fr: 'Bravo, vous avez trouvé !' },
    lose: { en: 'The word was ', es: 'La palabra era ', fr: 'Le mot était ' },
    copied: { en: 'Result copied — share it!', es: 'Resultado copiado, ¡compártelo!', fr: 'Résultat copié, partagez-le !' }
  };

  for (var r = 0; r < MAX; r++) {
    var row = document.createElement('div'); row.className = 'row';
    for (var c = 0; c < 5; c++) { var tl = document.createElement('div'); tl.className = 'tile'; row.appendChild(tl); }
    board.appendChild(row);
  }

  function score(guess) {
    var res = ['miss', 'miss', 'miss', 'miss', 'miss'], pool = {};
    for (var i = 0; i < 5; i++) {
      if (guess[i] === answer[i]) res[i] = 'hit';
      else pool[answer[i]] = (pool[answer[i]] || 0) + 1;
    }
    for (var j = 0; j < 5; j++) {
      if (res[j] !== 'hit' && pool[guess[j]]) { res[j] = 'near'; pool[guess[j]]--; }
    }
    return res;
  }

  function paint() {
    var rowEls = board.children;
    for (var r = 0; r < MAX; r++) {
      var word = r < rows.length ? rows[r] : (r === rows.length ? current : '');
      var res = r < rows.length ? score(rows[r]) : null;
      for (var c = 0; c < 5; c++) {
        var tl = rowEls[r].children[c];
        tl.textContent = word[c] || '';
        tl.className = 'tile' + (word[c] ? ' filled' : '') + (res ? ' ' + res[c] : '');
        tl.setAttribute('aria-label', (word[c] || '') + (res ? ' ' + res[c] : ''));
      }
    }
    var best = {};
    rows.forEach(function (w) {
      var s = score(w);
      for (var i = 0; i < 5; i++) {
        var rank = { hit: 3, near: 2, miss: 1 }[s[i]];
        if (!best[w[i]] || rank > best[w[i]]) best[w[i]] = rank;
      }
    });
    document.querySelectorAll('.key[data-k]').forEach(function (k) {
      var b = best[k.dataset.k];
      k.className = 'key' + (k.classList.contains('wide') ? ' wide' : '') + (b === 3 ? ' hit' : b === 2 ? ' near' : b === 1 ? ' miss' : '');
    });
  }

  function finish(won) {
    done = true;
    var stats = load('pw-stats', { played: 0, wins: 0, streak: 0, best: 0, last: 0 });
    if (!load(key + '-counted', false)) {
      stats.played++;
      if (won) { stats.wins++; stats.streak = (stats.last === num - 1 ? stats.streak : 0) + 1; stats.best = Math.max(stats.best, stats.streak); }
      else stats.streak = 0;
      stats.last = num; save('pw-stats', stats); save(key + '-counted', true);
    }
    document.getElementById('st-played').textContent = stats.played;
    document.getElementById('st-wins').textContent = stats.played ? Math.round(100 * stats.wins / stats.played) + '%' : '0%';
    document.getElementById('st-streak').textContent = stats.streak;
    document.getElementById('st-best').textContent = stats.best;
    document.getElementById('answer').textContent = answer;
    ['en', 'es', 'fr'].forEach(function (l, i) { document.getElementById('def-' + l).textContent = entry[i + 1]; });
    document.getElementById('reveal').classList.add('show');
    msg.textContent = won ? t(TXT.win) : t(TXT.lose) + answer;
  }

  function submit() {
    if (current.length < 5) {
      msg.textContent = t(TXT.short);
      var rowEl = board.children[rows.length]; rowEl.classList.add('shake');
      setTimeout(function () { rowEl.classList.remove('shake'); }, 400);
      return;
    }
    rows.push(current); current = ''; msg.textContent = '';
    save(key, rows); paint();
    if (rows[rows.length - 1] === answer) finish(true);
    else if (rows.length === MAX) finish(false);
  }

  function press(k) {
    if (done) return;
    if (k === 'ENTER') return submit();
    if (k === 'BACK') { current = current.slice(0, -1); return paint(); }
    if (/^[A-Z]$/.test(k) && current.length < 5) { current += k; paint(); }
  }

  document.querySelectorAll('.key').forEach(function (b) {
    b.addEventListener('click', function () { press(b.dataset.k || b.dataset.action); });
  });
  document.addEventListener('keydown', function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === 'Enter') press('ENTER');
    else if (e.key === 'Backspace') press('BACK');
    else if (/^[a-zA-Z]$/.test(e.key)) press(e.key.toUpperCase());
  });

  document.getElementById('share').addEventListener('click', function () {
    var grid = rows.map(function (w) {
      return score(w).map(function (s) { return s === 'hit' ? '\\uD83D\\uDFE5' : s === 'near' ? '\\uD83D\\uDFE8' : '\\u2B1C'; }).join('');
    }).join('\\n');
    var won = rows[rows.length - 1] === answer;
    var text = 'Madam CEO \\u00B7 Power Word #' + num + ' ' + (won ? rows.length : 'X') + '/6\\n' + grid + '\\n' + siteUrl + '/game/';
    if (navigator.share) { navigator.share({ text: text }).catch(function () {}); return; }
    try { navigator.clipboard.writeText(text).then(function () { msg.textContent = t(TXT.copied); }); } catch (e) {}
  });

  rows = load(key, []);
  paint();
  if (rows.length && (rows[rows.length - 1] === answer || rows.length === MAX)) finish(rows[rows.length - 1] === answer);
})();
"""
