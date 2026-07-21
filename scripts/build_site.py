#!/usr/bin/env python3
"""
Build script for Mine-JEPA static learning website.
Parses Markdown sources in site/content/<lang>/ and generates HTML pages in site/<lang>/.
Supports both 'fr' and 'en' languages.
"""

import os
import re
import html
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT_DIR / "site"
CONTENT_DIR = SITE_DIR / "content"

# Real slug mappings from frontmatter
SLUG_PAIR = {
    "01-c-est-quoi-jepa": "01-what-is-jepa",
    "02-le-piege-du-collapse": "02-the-collapse-trap",
    "03-le-modele-du-monde": "03-the-world-model",
    "04-planifier-en-imagination": "04-planning-in-imagination",
    "05-le-vrai-minecraft": "05-real-minecraft",
    "06-apprendre-a-fabriquer": "06-learning-to-craft",
    "07-la-curiosite-en-panne": "07-broken-curiosity",
    "08-le-mur-est-comportemental": "08-the-wall-is-behavioral",
    "09-les-prochaines-pistes": "09-next-directions",
}
# Inverse mapping
REVERSE_SLUG_PAIR = {v: k for k, v in SLUG_PAIR.items()}

CHAPTER_MEDIA = {
    5: {
        "gif": "agent_play_ebwm.gif",
        "alt_fr": "Vue à la première personne dans Minecraft : l'agent traverse une forêt dense, s'approche d'un tronc d'arbre et frappe avec son outil jusqu'à faire tomber l'arbre pour obtenir une bûche.",
        "caption_fr": "La cinquième tentative, en action — le meilleur épisode enregistré. Le taux de succès réel de la version publiée de cette politique est de 25% (5 épisodes sur 20) ; le meilleur run observé en interne (non publié) a atteint 50%. Ce n'est pas un agent qui coupe du bois à chaque tentative.",
        "alt_en": "First-person view in Minecraft: the agent walks through a dense forest, approaches a tree trunk, and strikes it with its tool until the tree breaks to yield a log.",
        "caption_en": "The fifth attempt in action — the best recorded episode. The actual success rate of the published policy version is 25% (5 out of 20 episodes); the best internally observed run (unpublished) hit 50%. This is not an agent that chops wood on every single attempt.",
    },
    6: {
        "gif": "agent_play_craft_demo.best.gif",
        "alt_fr": "Vue à la première personne dans Minecraft : l'agent commence avec du bois dans son inventaire, fabrique des planches, puis pose un établi et fabrique une pioche.",
        "caption_fr": "Fabrication réussie en direct — l'agent réutilise ses compétences visuelles et sa mémoire d'inventaire pour transformer le bois de départ en planches.",
        "alt_en": "First-person view in Minecraft: starting with wood in inventory, the agent crafts planks, places a crafting table, and crafts a pickaxe.",
        "caption_en": "Live crafting in action — the agent leverages its visual representation and inventory state memory to turn starting wood into planks.",
    },
    7: {
        "gif": "agent_play_explore.gif",
        "alt_fr": "Vue à la première personne dans Minecraft : l'agent explore un paysage vallonné en tournant la caméra et en s'avançant.",
        "caption_fr": "Le réflexe d'échantillonnage collant et de balayage de caméra en action lors de l'exploration.",
        "alt_en": "First-person view in Minecraft: the agent explores a hilly landscape, rotating its camera and stepping forward.",
        "caption_en": "Sticky sampling and camera scan reflexes in action during exploration.",
    },
    8: {
        "gif": "agent_play_craft_commit4.gif",
        "alt_fr": "Vue à la première personne dans Minecraft : l'agent enchaîne 4 actions consécutives par cycle de planification pour approcher et couper un arbre.",
        "caption_fr": "L'effet de commit_length=4 : l'agent tient ses gestes sur 4 pas consécutifs au lieu de réinitialiser à chaque pas.",
        "alt_en": "First-person view in Minecraft: the agent holds 4 consecutive actions per planning cycle to approach and chop a tree.",
        "caption_en": "The effect of commit_length=4: holding gestures over 4 consecutive steps instead of resetting every single step.",
    },
}

def parse_frontmatter(text):
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            yaml_text = parts[1]
            body = parts[2]
            meta = {}
            for line in yaml_text.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip()
                    if v.startswith('"') and v.endswith('"'):
                        v = v[1:-1]
                    elif v.startswith("'") and v.endswith("'"):
                        v = v[1:-1]
                    elif v.startswith("[") and v.endswith("]"):
                        items = [x.strip().strip('"').strip("'") for x in v[1:-1].split(",") if x.strip()]
                        v = items
                    elif v.isdigit():
                        v = int(v)
                    meta[k] = v
            return meta, body
    return {}, text

def markdown_to_html(md):
    """Converts Markdown prose to HTML."""
    lines = md.strip().split("\n")
    out = []
    in_code = False
    code_lang = ""
    code_lines = []
    in_list = False
    list_type = None
    in_table = False
    table_lines = []
    in_quote = False
    quote_lines = []

    def flush_list():
        nonlocal in_list, list_type
        if in_list:
            out.append(f"</{list_type}>")
            in_list = False
            list_type = None

    def flush_quote():
        nonlocal in_quote, quote_lines
        if in_quote:
            q_text = markdown_to_html("\n".join(quote_lines))
            out.append(f'<div class="callout">\n{q_text}\n</div>')
            in_quote = False
            quote_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if in_table:
            rows = []
            for tline in table_lines:
                cells = [c.strip() for c in tline.strip("|").split("|")]
                rows.append(cells)
            if len(rows) >= 2:
                headers = rows[0]
                data_rows = rows[2:]
                th_html = "".join(f"<th>{render_inline(c)}</th>" for c in headers)
                tbody_html = ""
                for r in data_rows:
                    td_html = "".join(f"<td>{render_inline(c)}</td>" for c in r)
                    tbody_html += f"<tr>{td_html}</tr>\n"
                out.append(f"<table>\n<thead><tr>{th_html}</tr></thead>\n<tbody>\n{tbody_html}</tbody>\n</table>")
            in_table = False
            table_lines = []

    def render_inline(txt):
        txt = html.escape(txt)
        txt = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", txt)
        txt = re.sub(r"\*(.*?)\*", r"<em>\1</em>", txt)
        txt = re.sub(r"_(.*?)_", r"<em>\1</em>", txt)
        txt = re.sub(r"`(.*?)`", r"<code>\1</code>", txt)
        txt = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', txt)
        return txt

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                c_content = html.escape("\n".join(code_lines))
                out.append(f"<pre><code>{c_content}</code></pre>")
                in_code = False
                code_lines = []
            else:
                flush_list()
                flush_quote()
                flush_table()
                in_code = True
                code_lang = stripped[3:].strip()
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_list()
            flush_quote()
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append(stripped)
            continue
        elif in_table:
            flush_table()

        if stripped.startswith("> "):
            flush_list()
            flush_table()
            if not in_quote:
                in_quote = True
                quote_lines = []
            quote_lines.append(line[2:])
            continue
        elif in_quote:
            flush_quote()

        if stripped.startswith("## "):
            flush_list()
            out.append(f"<h2>{render_inline(stripped[3:])}</h2>")
            continue
        elif stripped.startswith("### "):
            flush_list()
            out.append(f"<h3>{render_inline(stripped[4:])}</h3>")
            continue
        elif stripped.startswith("#### "):
            flush_list()
            out.append(f"<h4>{render_inline(stripped[5:])}</h4>")
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_quote()
            flush_table()
            if not in_list or list_type != "ul":
                flush_list()
                in_list = True
                list_type = "ul"
                out.append("<ul>")
            out.append(f"<li>{render_inline(stripped[2:])}</li>")
            continue
        elif re.match(r"^\d+\.\s", stripped):
            flush_quote()
            flush_table()
            item_text = re.sub(r"^\d+\.\s", "", stripped)
            if not in_list or list_type != "ol":
                flush_list()
                in_list = True
                list_type = "ol"
                out.append("<ol>")
            out.append(f"<li>{render_inline(item_text)}</li>")
            continue
        else:
            flush_list()

        if not stripped:
            continue

        out.append(f"<p>{render_inline(stripped)}</p>")

    flush_list()
    flush_quote()
    flush_table()

    return "\n".join(out)

def process_tracks(body_md, lang):
    beginner_kicker = "Piste débutant" if lang == "fr" else "Beginner track"
    expert_kicker = "Piste expert" if lang == "fr" else "Expert track"

    beginner_md = ""
    expert_md = ""

    parts = body_md.split("::: beginner")
    if len(parts) > 1:
        rest = parts[1]
        subparts = rest.split("::: expert")
        beginner_md = subparts[0].replace(":::", "").strip()
        if len(subparts) > 1:
            expert_md = subparts[1].replace(":::", "").strip()

    beg_html = markdown_to_html(beginner_md)
    exp_html = markdown_to_html(expert_md)

    tracks_html = f"""
      <div class="tracks" data-tracks>
        <div class="track-tabs" role="tablist" aria-label="{'Niveau de lecture' if lang == 'fr' else 'Reading level'}">
          <button class="track-tab" role="tab" id="tab-beginner" aria-controls="panel-beginner" aria-selected="true" data-track-tab="beginner">{'Débutant' if lang == 'fr' else 'Beginner'}</button>
          <button class="track-tab" role="tab" id="tab-expert" aria-controls="panel-expert" aria-selected="false" tabindex="-1" data-track-tab="expert">{'Expert' if lang == 'fr' else 'Expert'}</button>
        </div>

        <div class="track-panel is-active chapter-prose" data-track-panel="beginner" role="tabpanel" id="panel-beginner" aria-labelledby="tab-beginner">
          <p class="track-kicker">{beginner_kicker}</p>

{beg_html}
        </div>

        <div class="track-panel chapter-prose" data-track-panel="expert" role="tabpanel" id="panel-expert" aria-labelledby="tab-expert">
          <p class="track-kicker">{expert_kicker}</p>

{exp_html}
        </div>
      </div>
"""
    return tracks_html

def build_chapter_html(meta, body_md, lang):
    order = meta.get("order", 1)
    title = meta.get("title", "")
    slug = meta.get("slug", "")

    if lang == "fr":
        other_lang = "en"
        other_slug = SLUG_PAIR.get(slug, slug)
        fr_href = f"{slug}.html"
        en_href = f"../en/{other_slug}.html"
        fr_current = ' aria-current="true"'
        en_current = ''
        fr_title = 'FR'
        en_title = 'EN'
        site_title = f"{title} — Mine-JEPA"
        desc = f"Chapitre {order} du parcours Mine-JEPA : {title}."
        breadcrumb_label = "Fil d'Ariane"
        path_link_text = "Parcours d'apprentissage"
        chap_kicker = f"Chapitre {order}"
        track_pref_label = "Afficher :"
        beg_label = "Débutant"
        exp_label = "Expert"
    else:
        other_lang = "fr"
        other_slug = REVERSE_SLUG_PAIR.get(slug, slug)
        fr_href = f"../fr/{other_slug}.html"
        en_href = f"{slug}.html"
        fr_current = ''
        en_current = ' aria-current="true"'
        fr_title = 'FR'
        en_title = 'EN'
        site_title = f"{title} — Mine-JEPA"
        desc = f"Chapter {order} of the Mine-JEPA learning path: {title}."
        breadcrumb_label = "Breadcrumbs"
        path_link_text = "Learning Path"
        chap_kicker = f"Chapter {order}"
        track_pref_label = "Show:"
        beg_label = "Beginner"
        exp_label = "Expert"

    tracks_content = process_tracks(body_md, lang)

    if lang == "fr":
        if order == 1:
            prereq_text = "Aucun prérequis — c'est le point de départ du parcours."
        elif order == 6:
            prereq_text = "Prérequis : Chapitres 1 à 5 — l'encodeur, les garde-fous anti-collapse, le world model, le planificateur, et le premier succès en vrai Minecraft."
        elif order == 7:
            prereq_text = "Prérequis : Chapitres 1 à 6 — jusqu'au mur du premier arbre trouvé en solo, que ce chapitre attaque pour la première fois."
        elif order == 8:
            prereq_text = "Prérequis : Chapitres 1 à 7 — y compris les deux premières tentatives, échouées, de trouver seul le premier arbre."
        elif order == 9:
            prereq_text = "Prérequis : Chapitres 1 à 8 — dont l'attempt #8 (pistes A et C, désormais testées et NO-GO, voir Chapitre 8)."
        else:
            prereq_text = f"Prérequis : Chapitres 1 à {order-1}."
    else:
        if order == 1:
            prereq_text = "No prerequisites — this is the starting point of the path."
        elif order == 6:
            prereq_text = "Prerequisites: Chapters 1 to 5 — the encoder, anti-collapse safeguards, world model, planner, and first success in real Minecraft."
        elif order == 7:
            prereq_text = "Prerequisites: Chapters 1 to 6 — up to the wall of finding the first tree solo, which this chapter attacks for the first time."
        elif order == 8:
            prereq_text = "Prerequisites: Chapters 1 to 7 — including the first two failed attempts to find the first tree solo."
        elif order == 9:
            prereq_text = "Prerequisites: Chapters 1 to 8 — including attempt #8 (avenues A and C, now tested and NO-GO, see Chapter 8)."
        else:
            prereq_text = f"Prerequisites: Chapters 1 to {order-1}."

    media_html = ""
    if order in CHAPTER_MEDIA:
        m = CHAPTER_MEDIA[order]
        gif = m["gif"]
        alt = m[f"alt_{lang}"]
        cap = m[f"caption_{lang}"]
        media_html = f"""
      <figure class="chapter-media">
        <img
          src="../assets/{gif}"
          width="64"
          height="64"
          alt="{html.escape(alt)}">
        <figcaption>
          {html.escape(cap)}
        </figcaption>
      </figure>
"""

    footer_text = "Mine-JEPA — un agent JEPA qui apprend à jouer à Minecraft à partir des pixels, documenté au fil de l'eau." if lang == "fr" else "Mine-JEPA — a JEPA agent learning to play Minecraft from pixels, documented along the way."

    html_content = f"""<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(site_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="stylesheet" href="../style.css">
<script>document.documentElement.classList.add("js");</script>
</head>
<body>
<a class="skip-link" href="#main">{'Aller au contenu' if lang == 'fr' else 'Skip to content'}</a>

<header class="site-header">
  <div class="wrap site-header-inner">
    <a class="site-brand" href="index.html"><span class="brand-mark" aria-hidden="true">&#9935;</span> Mine-JEPA</a>
    <div class="header-controls">
      <nav class="lang-switch" aria-label="{'Langue du site' if lang == 'fr' else 'Site language'}">
        <a href="{fr_href}"{fr_current} lang="fr" hreflang="fr">{fr_title}</a>
        <a href="{en_href}"{en_current} lang="en" hreflang="en">{en_title}</a>
      </nav>
      <div class="track-pref" data-track-pref>
        <span class="track-pref-label" id="track-pref-label">{track_pref_label}</span>
        <button type="button" data-track-pref-value="beginner" aria-pressed="true" aria-describedby="track-pref-label">{beg_label}</button>
        <button type="button" data-track-pref-value="expert" aria-pressed="false" aria-describedby="track-pref-label">{exp_label}</button>
      </div>
    </div>
  </div>
</header>

<main id="main">

  <nav class="breadcrumb" aria-label="{breadcrumb_label}">
    <div class="wrap">
      <a href="index.html">{path_link_text}</a>
      <span aria-hidden="true">/</span>
      <span>{chap_kicker}</span>
    </div>
  </nav>

  <article class="chapter">
    <div class="wrap">

      <header class="chapter-header">
        <p class="chapter-kicker">{chap_kicker}</p>
        <h1>{html.escape(title)}</h1>
        <p class="chapter-prereqs">{html.escape(prereq_text)}</p>
      </header>
{media_html}
{tracks_content}

    </div>
  </article>

</main>

<footer class="site-footer">
  <div class="wrap">
    <p>{footer_text}</p>
  </div>
</footer>

<script src="../script.js" defer></script>
</body>
</html>
"""
    return html_content

def generate_en_landing_page(chapters_meta):
    """Generates site/en/index.html using the tech-tree layout in English."""
    nodes_html = ""
    for ch in sorted(chapters_meta, key=lambda x: x["order"]):
        order = ch["order"]
        title = ch["title"]
        slug = ch["slug"]

        recipe_html = ""
        if order == 1:
            recipe_html = """          <div class="recipe-row" aria-hidden="true">
            <div class="recipe-slot recipe-slot-output">1</div>
          </div>"""
        else:
            slots = ""
            for p in range(1, order):
                slots += f'            <div class="recipe-slot recipe-slot-prereq" title="Chapter {p}">{p}</div>\n'
            recipe_html = f"""          <div class="recipe-row" aria-hidden="true">
{slots}            <div class="recipe-arrow">&#10141;</div>
            <div class="recipe-slot recipe-slot-output">{order}</div>
          </div>"""

        if order == 1:
            prereq_desc = "No prerequisites — this is the starting point of the path."
        elif order == 2:
            prereq_desc = 'Prerequisites: Chapter 1, "What is JEPA, and why train a program to play Minecraft with it?"'
        elif order == 3:
            prereq_desc = 'Prerequisites: Chapter 1, "What is JEPA, and why train a program to play Minecraft with it?" and Chapter 2, "The shortcut the model always tries to find (and how we prevent it)"'
        elif order == 4:
            prereq_desc = 'Prerequisites: Chapters 1 to 3 — the encoder, anti-collapse safeguards, and world model.'
        elif order == 5:
            prereq_desc = 'Prerequisites: Chapters 1 to 4 — encoder, anti-collapse safeguards, world model, and imagination planner.'
        elif order == 6:
            prereq_desc = "Prerequisites: Chapters 1 to 5 — encoder, anti-collapse safeguards, world model, planner, and the first success in real Minecraft."
        elif order == 7:
            prereq_desc = "Prerequisites: Chapters 1 to 6 — up to the wall of finding the first tree solo, which this chapter attacks for the first time."
        elif order == 8:
            prereq_desc = "Prerequisites: Chapters 1 to 7 — including the first two failed attempts to find the first tree solo."
        elif order == 9:
            prereq_desc = "Prerequisites: Chapters 1 to 8 — including attempt #8 (avenues A and C, now tested and NO-GO, see Chapter 8). This chapter distinguishes acquired results from an unexecuted plan (learned policy and two refinements)."

        extra_badge = ' <span class="badge badge-plan">Not yet launched</span>' if order == 9 else ""

        nodes_html += f"""
        <li class="tech-node">
{recipe_html}
          <div class="node-card">
            <p class="node-meta">
              <span class="badge badge-order">Chapter {order}</span>{extra_badge}
            </p>
            <h3 class="node-title">
              <a href="{slug}.html">{html.escape(title)}</a>
            </h3>
            <p class="node-prereqs">
              {html.escape(prereq_desc)}
            </p>
          </div>
        </li>
"""

    index_html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mine-JEPA — learning JEPA through a real Minecraft agent</title>
<meta name="description" content="Mine-JEPA teaches JEPA (Joint-Embedding Predictive Architecture) through the ongoing real story of an agent learning to play Minecraft from pixels — successes and failures included, written side-by-side for beginners and experts.">
<link rel="stylesheet" href="../style.css">
<script>document.documentElement.classList.add("js");</script>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>

<header class="site-header">
  <div class="wrap site-header-inner">
    <a class="site-brand" href="index.html"><span class="brand-mark" aria-hidden="true">&#9935;</span> Mine-JEPA</a>
    <div class="header-controls">
      <nav class="lang-switch" aria-label="Site language">
        <a href="../fr/index.html" lang="fr" hreflang="fr">FR</a>
        <a href="index.html" aria-current="true" lang="en" hreflang="en">EN</a>
      </nav>
      <div class="track-pref" data-track-pref>
        <span class="track-pref-label" id="track-pref-label">Show:</span>
        <button type="button" data-track-pref-value="beginner" aria-pressed="true" aria-describedby="track-pref-label">Beginner</button>
        <button type="button" data-track-pref-value="expert" aria-pressed="false" aria-describedby="track-pref-label">Expert</button>
      </div>
    </div>
  </div>
</header>

<main id="main">

  <section class="hero">
    <div class="wrap hero-grid">
      <div class="hero-copy">
        <p class="eyebrow">A real research journal, in progress</p>
        <h1>Watch a JEPA agent learn to play Minecraft — and understand how it works, chapter by chapter</h1>
        <p class="lede">
          Mine-JEPA is a lightweight JEPA (Joint-Embedding Predictive Architecture)
          trained directly on game images, built to plan its own actions rather than reacting blindly.
          This site tells the story of how it was built, in the order it actually happened — including
          the parts that didn't work. Each chapter is written twice: once for a curious beginner,
          once for someone who already knows machine learning. Pick a track, switch anytime.
        </p>
        <a class="button" href="#path">Start the journey</a>
      </div>
      <figure class="hero-media">
        <img
          src="../assets/agent_play_ebwm.gif"
          width="64"
          height="64"
          alt="First-person view in Minecraft: the agent walks through a dense forest, approaches a tree trunk, and strikes it with its tool until the tree breaks to yield a log.">
        <figcaption>
          Real footage from <code>MineRLTreechop-v0</code>: the agent, guided by its JEPA world model,
          plans its approach to a tree and chops it down to obtain a log. This is the best recorded
          episode among those evaluated — the actual success rate of this policy is between 1-in-4 and
          1-in-2, not every single attempt.
        </figcaption>
      </figure>
    </div>
  </section>

  <section class="section" id="path" aria-labelledby="path-heading">
    <div class="wrap">
      <h2 id="path-heading">The Tech Tree</h2>
      <p class="section-intro">
        Chapters follow the project in the order it actually unfolded: each builds on the ideas
        and results of the previous one — like a crafting recipe where each slot only unlocks once
        its ingredients are gathered.
      </p>

      <ol class="tech-tree">
{nodes_html}
      </ol>

      <p class="section-intro section-note">
        The journey stops honestly where writing stops today: no future slots have been added in advance.
      </p>
    </div>
  </section>

  <section class="section" aria-labelledby="honesty-heading">
    <div class="wrap">
      <h2 id="honesty-heading">Why this feels like a lab notebook, not a showreel</h2>
      <div class="callout">
        <p>
          Mine-JEPA is a real, ongoing project, and this site is written directly from its research
          log — including attempts that failed, partially conclusive results, and problems nobody
          has solved yet. If a chapter reports a negative result, it remains a negative result here:
          no forced enthusiasm, no confetti. The honest version of this story is also the most
          interesting.
        </p>
      </div>
    </div>
  </section>

</main>

<footer class="site-footer">
  <div class="wrap">
    <p>Mine-JEPA — a JEPA agent learning to play Minecraft from pixels, documented along the way.</p>
  </div>
</footer>

<script src="../script.js" defer></script>
</body>
</html>
"""
    return index_html

def update_fr_html_assets_and_nav():
    """Fixes image asset paths in site/fr/*.html to ../assets/ and updates language switches."""
    fr_dir = SITE_DIR / "fr"
    if not fr_dir.exists():
        return
    for fpath in fr_dir.glob("*.html"):
        content = fpath.read_text(encoding="utf-8")

        # Fix asset paths: ../../assets/ -> ../assets/
        content = content.replace("../../assets/", "../assets/")

        # Update language switcher
        if fpath.name == "index.html":
            new_nav = '''      <nav class="lang-switch" aria-label="Langue du site">
        <a href="index.html" aria-current="true" lang="fr" hreflang="fr">FR</a>
        <a href="../en/index.html" lang="en" hreflang="en">EN</a>
      </nav>'''
        else:
            fr_slug = fpath.stem
            en_slug = SLUG_PAIR.get(fr_slug, fr_slug)
            new_nav = f'''      <nav class="lang-switch" aria-label="Langue du site">
        <a href="{fr_slug}.html" aria-current="true" lang="fr" hreflang="fr">FR</a>
        <a href="../en/{en_slug}.html" lang="en" hreflang="en">EN</a>
      </nav>'''
        
        old_pattern = r'<nav class="lang-switch".*?</nav>'
        updated_content = re.sub(old_pattern, new_nav, content, flags=re.DOTALL)
        fpath.write_text(updated_content, encoding="utf-8")
        print(f"Updated {fpath.relative_to(SITE_DIR)}")

def build():
    en_content_dir = CONTENT_DIR / "en"
    en_site_dir = SITE_DIR / "en"
    en_site_dir.mkdir(parents=True, exist_ok=True)

    en_chapters = []

    for md_file in sorted(en_content_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        meta, body_md = parse_frontmatter(text)
        en_chapters.append(meta)

        html_out = build_chapter_html(meta, body_md, lang="en")
        slug = meta.get("slug", md_file.stem)
        out_file = en_site_dir / f"{slug}.html"
        out_file.write_text(html_out, encoding="utf-8")
        print(f"Generated {out_file.relative_to(SITE_DIR)}")

    # Build en/index.html
    en_index_html = generate_en_landing_page(en_chapters)
    (en_site_dir / "index.html").write_text(en_index_html, encoding="utf-8")
    print("Generated en/index.html")

    # Fix image asset paths and update language switches in site/fr/
    update_fr_html_assets_and_nav()

if __name__ == "__main__":
    build()
