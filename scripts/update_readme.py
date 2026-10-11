#!/usr/bin/env python3
"""Atualiza a seção de tecnologias do README com base nos repositórios públicos.

Como funciona:
  1. Lista os repositórios públicos do usuário (ignora forks e o repositório do perfil).
  2. Soma os bytes de código por linguagem.
  3. Olha os arquivos da raiz de cada repositório (package.json, pom.xml,
     requirements.txt, project.godot, ProjectSettings, vercel.json, workflows...)
     para detectar frameworks, testes, IA e deploy.
  4. Reescreve tudo o que estiver entre <!--TECH:START--> e <!--TECH:END--> no README.

Só usa a biblioteca padrão do Python. Variáveis de ambiente (todas opcionais):
  GH_USER       usuário do GitHub (padrão: GianluccaPaiva)
  GITHUB_TOKEN  token para aumentar o limite da API (o Actions já fornece um)
  README_PATH   caminho do README (padrão: README.md)
  IGNORE_REPOS  nomes de repositórios a ignorar, separados por vírgula
  EXTRA_REPOS   repositórios de outras contas/organizações em que você trabalha,
                no formato dono/nome, separados por vírgula
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from urllib.parse import quote

USER = os.environ.get("GH_USER", "GianluccaPaiva")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")
START, END = "<!--TECH:START-->", "<!--TECH:END-->"
IGNORE_REPOS = {USER.lower()} | {
    r.strip().lower() for r in os.environ.get("IGNORE_REPOS", "").split(",") if r.strip()
}
# Projetos de outras contas ou organizações em que você participa (públicos).
EXTRA_REPOS = [
    r.strip()
    for r in os.environ.get(
        "EXTRA_REPOS", "NexusMindCorp/NexusClass,igorknop/jbufjf-mobile"
    ).split(",")
    if r.strip()
]
# Linguagens que o GitHub detecta, mas que não representam uma habilidade a destacar.
IGNORE_LANGS = {"ShaderLab", "HLSL", "Batchfile", "PowerShell", "Shell", "Makefile", "Dockerfile"}

# nome exibido -> (logo do simple-icons, cor, cor do logo)
ICONS = {
    # Linguagens
    "Java": ("openjdk", "ED8B00", "white"),
    "TypeScript": ("typescript", "3178C6", "white"),
    "JavaScript": ("javascript", "F7DF1E", "black"),
    "Python": ("python", "3776AB", "white"),
    "C++": ("cplusplus", "00599C", "white"),
    "C": ("c", "A8B9CC", "black"),
    "C#": ("csharp", "512BD4", "white"),
    "GDScript": ("godotengine", "478CBF", "white"),
    "HTML": ("html5", "E34F26", "white"),
    "CSS": ("css3", "1572B6", "white"),
    "Kotlin": ("kotlin", "7F52FF", "white"),
    "Go": ("go", "00ADD8", "white"),
    "Rust": ("rust", "000000", "white"),
    "PHP": ("php", "777BB4", "white"),
    "SQL": ("postgresql", "336791", "white"),
    # Frameworks e bibliotecas
    "React": ("react", "20232A", "61DAFB"),
    "React Native": ("react", "20232A", "61DAFB"),
    "Expo": ("expo", "000020", "white"),
    "Vite": ("vite", "646CFF", "white"),
    "Next.js": ("nextdotjs", "000000", "white"),
    "Tailwind CSS": ("tailwindcss", "06B6D4", "white"),
    "NativeWind": ("tailwindcss", "0F172A", "38BDF8"),
    "shadcn/ui": ("shadcnui", "000000", "white"),
    "Spring": ("spring", "6DB33F", "white"),
    "Unity": ("unity", "000000", "white"),
    "Godot": ("godotengine", "478CBF", "white"),
    "FastAPI": ("fastapi", "009688", "white"),
    "Flask": ("flask", "000000", "white"),
    "Django": ("django", "092E20", "white"),
    "CustomTkinter": ("python", "3776AB", "white"),
    # IA e dados
    "Gemini": ("googlegemini", "8E75B2", "white"),
    "OpenAI": ("openai", "412991", "white"),
    "Whisper": ("openai", "412991", "white"),
    "NumPy": ("numpy", "013243", "white"),
    "Pandas": ("pandas", "150458", "white"),
    "TensorFlow": ("tensorflow", "FF6F00", "white"),
    "PyTorch": ("pytorch", "EE4C2C", "white"),
    # Testes
    "JUnit": ("junit5", "25A162", "white"),
    "Jest": ("jest", "C21325", "white"),
    "Vitest": ("vitest", "6E9F18", "white"),
    "Cypress": ("cypress", "17202C", "white"),
    "Playwright": ("playwright", "2EAD33", "white"),
    "Selenium": ("selenium", "43B02A", "white"),
    "Pytest": ("pytest", "0A9EDC", "white"),
    # Build e deploy
    "Maven": ("apachemaven", "C71A36", "white"),
    "GitHub Actions": ("githubactions", "2088FF", "white"),
    "Vercel": ("vercel", "000000", "white"),
    "Docker": ("docker", "2496ED", "white"),
    "Supabase": ("supabase", "3FCF8E", "white"),
}

CATEGORY = {}
for _n in ("React", "React Native", "Expo", "Vite", "Next.js", "Tailwind CSS", "NativeWind",
           "shadcn/ui", "Spring", "Unity", "Godot", "FastAPI", "Flask", "Django", "CustomTkinter"):
    CATEGORY[_n] = "Frameworks e bibliotecas"
for _n in ("Gemini", "OpenAI", "Whisper", "NumPy", "Pandas", "TensorFlow", "PyTorch"):
    CATEGORY[_n] = "IA e dados"
for _n in ("JUnit", "Jest", "Vitest", "Cypress", "Playwright", "Selenium", "Pytest"):
    CATEGORY[_n] = "Testes e automação"
for _n in ("Maven", "GitHub Actions", "Vercel", "Docker", "Supabase"):
    CATEGORY[_n] = "Build e deploy"
ORDER = ["Linguagens", "Frameworks e bibliotecas", "IA e dados", "Testes e automação", "Build e deploy"]

NPM = {
    "react": "React", "react-native": "React Native", "expo": "Expo", "vite": "Vite",
    "next": "Next.js", "tailwindcss": "Tailwind CSS", "nativewind": "NativeWind",
    "jest": "Jest", "vitest": "Vitest", "cypress": "Cypress",
    "playwright": "Playwright", "@playwright/test": "Playwright",
    "selenium-webdriver": "Selenium",
    "@supabase/supabase-js": "Supabase",
    "@google/genai": "Gemini", "@google/generative-ai": "Gemini",
    "openai": "OpenAI",
}
PIP = {
    "pytest": "Pytest", "selenium": "Selenium", "playwright": "Playwright",
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "customtkinter": "CustomTkinter", "google-generativeai": "Gemini", "google-genai": "Gemini",
    "openai": "OpenAI", "faster-whisper": "Whisper", "openai-whisper": "Whisper",
    "numpy": "NumPy", "pandas": "Pandas", "tensorflow": "TensorFlow", "torch": "PyTorch",
}
TOPICS = {
    "react": "React", "react-native": "React Native", "expo": "Expo", "vite": "Vite",
    "nextjs": "Next.js", "tailwindcss": "Tailwind CSS", "shadcn-ui": "shadcn/ui",
    "spring": "Spring", "spring-boot": "Spring", "unity": "Unity", "godot": "Godot",
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django", "docker": "Docker",
    "junit": "JUnit", "jest": "Jest", "vitest": "Vitest", "cypress": "Cypress",
    "playwright": "Playwright", "selenium": "Selenium", "pytest": "Pytest",
    "gemini": "Gemini", "openai": "OpenAI", "maven": "Maven", "supabase": "Supabase",
}


# --------------------------------------------------------------------------- API
def api(path, raw=False):
    """GET na API do GitHub. Devolve None para 404/409 (arquivo ou repositório vazio)."""
    req = urllib.request.Request("https://api.github.com" + path)
    req.add_header("Accept", "application/vnd.github.raw+json" if raw else "application/vnd.github+json")
    req.add_header("User-Agent", "readme-tech-updater")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        if err.code in (404, 409):
            return None
        raise
    return body if raw else json.loads(body)


def list_repos(get):
    repos, page = [], 1
    while True:
        batch = get(f"/users/{USER}/repos?per_page=100&type=owner&page={page}") or []
        repos += batch
        if len(batch) < 100:
            return repos
        page += 1


# --------------------------------------------------------------------- detecção
def detect(repo, get):
    """Devolve (bytes por linguagem, conjunto de tecnologias) de um repositório."""
    base = f"/repos/{repo['full_name']}"
    techs = {TOPICS[t] for t in repo.get("topics", []) if t in TOPICS}
    langs = get(f"{base}/languages") or {}

    root = get(f"{base}/contents/") or []
    files = {item["name"]: item.get("type") for item in root if isinstance(item, dict)}

    if "package.json" in files:
        try:
            pkg = json.loads(get(f"{base}/contents/package.json", raw=True) or "{}")
        except ValueError:
            pkg = {}
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        techs |= {NPM[d] for d in deps if d in NPM}
        if any(d.startswith("@rn-primitives") for d in deps):
            techs.add("shadcn/ui")
    if "components.json" in files:
        techs.add("shadcn/ui")
    if "pom.xml" in files:
        techs.add("Maven")
        pom = (get(f"{base}/contents/pom.xml", raw=True) or "").lower()
        if "org.springframework" in pom or "spring-boot" in pom:
            techs.add("Spring")
        if "junit" in pom:
            techs.add("JUnit")
    for req_file in ("requirements.txt", "requirements-dev.txt"):
        if req_file in files:
            for line in (get(f"{base}/contents/{req_file}", raw=True) or "").splitlines():
                pkg_name = re.split(r"[=<>~!\[;\s]", line.strip().lower(), maxsplit=1)[0]
                if pkg_name in PIP:
                    techs.add(PIP[pkg_name])
    if files.get("supabase") == "dir":
        techs.add("Supabase")
    if "project.godot" in files:
        techs.add("Godot")
    if files.get("ProjectSettings") == "dir":
        techs.add("Unity")
    if "vercel.json" in files:
        techs.add("Vercel")
    if "Dockerfile" in files or "docker-compose.yml" in files:
        techs.add("Docker")
    if files.get(".github") == "dir" and get(f"{base}/contents/.github/workflows"):
        techs.add("GitHub Actions")
    return langs, techs


def collect(get):
    lang_bytes, tech_count, used = Counter(), Counter(), []
    repos = list_repos(get)
    for spec in EXTRA_REPOS:
        extra = get(f"/repos/{spec}")
        if extra:  # None se o repositório for privado ou não existir
            repos.append(extra)
    seen = set()
    for repo in repos:
        if repo["full_name"].lower() in seen:
            continue
        seen.add(repo["full_name"].lower())
        if repo.get("fork") or repo.get("archived") or repo["name"].lower() in IGNORE_REPOS:
            continue
        langs, techs = detect(repo, get)
        used.append(repo["full_name"])
        for lang, size in langs.items():
            if lang not in IGNORE_LANGS:
                lang_bytes[lang] += size
        tech_count.update(techs)
    return lang_bytes, tech_count, used


# ---------------------------------------------------------------------- render
def badge(name):
    logo, color, logo_color = ICONS.get(name, ("", "555555", "white"))
    label = quote(name.replace("-", "--").replace("_", "__"), safe="")
    url = f"https://img.shields.io/badge/{label}-{color}?style=flat-square"
    if logo:
        url += f"&logo={logo}&logoColor={logo_color}"
    return f"![{name}]({url})"


def render(lang_bytes, tech_count):
    rows = {cat: [] for cat in ORDER}
    rows["Linguagens"] = [lang for lang, _ in lang_bytes.most_common()]
    for tech, _ in sorted(tech_count.items(), key=lambda kv: (-kv[1], kv[0])):
        rows[CATEGORY.get(tech, "Frameworks e bibliotecas")].append(tech)
    lines = ["| Área | Tecnologias |", "|---|---|"]
    for cat in ORDER:
        if rows[cat]:
            lines.append(f"| **{cat}** | " + " ".join(badge(t) for t in rows[cat]) + " |")
    return "\n".join(lines)


def update_readme(table):
    with open(README, encoding="utf-8") as fh:
        text = fh.read()
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        sys.exit(f"Marcadores {START} e {END} não encontrados em {README}.")
    new_block = f"{START}\n{table}\n{END}"
    new_text = pattern.sub(lambda _m: new_block, text, count=1)
    if new_text != text:
        with open(README, "w", encoding="utf-8") as fh:
            fh.write(new_text)
    return new_text != text


def main():
    lang_bytes, tech_count, used = collect(api)
    if not lang_bytes and not tech_count:
        sys.exit("Nenhuma tecnologia encontrada; README mantido sem alterações.")
    changed = update_readme(render(lang_bytes, tech_count))
    print(f"{len(used)} repositórios analisados; README {'atualizado' if changed else 'já estava atualizado'}.")


if __name__ == "__main__":
    main()
