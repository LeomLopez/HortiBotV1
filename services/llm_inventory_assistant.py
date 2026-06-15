import json
import re
import unicodedata
from datetime import date, datetime, timedelta
from urllib import error, request

from config.config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT_SECONDS
from models.db import obtener_stock_actual, obtener_stock_vencido
from views.formatters import _fmt_fecha


HORTI_GROUPS = {"HOR", "FRU", "LAC"}
GROUP_LABELS = {
    "HOR": "Hortaliças",
    "FRU": "Frutas",
    "LAC": "Laticínios",
}
GROUP_ALIASES = {
    "hortifruti": "ALL",
    "horti": "ALL",
    "hortalicas": "HOR",
    "hortalica": "HOR",
    "verduras": "HOR",
    "verdura": "HOR",
    "legumes": "HOR",
    "legume": "HOR",
    "hor": "HOR",
    "frutas": "FRU",
    "fruta": "FRU",
    "fru": "FRU",
    "laticinios": "LAC",
    "laticinio": "LAC",
    "lacteos": "LAC",
    "lacteo": "LAC",
    "lac": "LAC",
}


def answer_hortifruti_question(question: str) -> str:
    text = (question or "").strip()
    if not text:
        return (
            "Use assim: `/ai quanto tenho de tomate?`\n"
            "Também posso responder sobre frutas, hortaliças, laticínios e vencimentos."
        )

    plan = _fallback_plan(text)
    if plan.get("intent") == "help":
        plan = _llm_plan(text) or plan

    intent = plan.get("intent")
    if intent == "stock_product":
        return _answer_product_stock(plan.get("product") or text)
    if intent == "stock_group":
        return _answer_group_stock(plan.get("groups") or _groups_from_text(text))
    if intent == "expiring":
        return _answer_expiring(days=_safe_days(plan.get("days")))
    if intent == "expired":
        return _answer_expired()

    return (
        "Posso consultar o inventário de Hortifruti em modo leitura.\n"
        "Exemplos:\n"
        "• `/ai quanto tem de tomate?`\n"
        "• `/ai quais frutas tenho?`\n"
        "• `/ai o que vence nos próximos 2 dias?`"
    )


def _llm_plan(question: str) -> dict | None:
    prompt = (
        "Você transforma perguntas de inventário em JSON. "
        "Responda somente JSON válido, sem markdown.\n"
        "Intenções permitidas: stock_product, stock_group, expiring, expired, help.\n"
        "Grupos permitidos: HOR para hortaliças/verduras/legumes, "
        "FRU para frutas, LAC para laticínios.\n"
        "Campos: intent, product, groups, days.\n"
        "Nunca traduza nomes de produtos. Copie o produto no mesmo idioma da pergunta.\n"
        "Se a pergunta pedir um produto específico, use stock_product.\n"
        "Se pedir lista por categoria, use stock_group.\n"
        "Se perguntar vencimentos futuros, use expiring.\n"
        "Se perguntar vencidos, use expired.\n\n"
        f"Pergunta: {question}"
    )

    payload = json.dumps(
        {
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
    ).encode("utf-8")

    url = LLM_BASE_URL.rstrip("/") + "/api/generate"
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:
        with request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    raw = (data.get("response") or "").strip()
    parsed = _extract_json_object(raw)
    if not parsed:
        return None

    intent = parsed.get("intent")
    if intent not in {"stock_product", "stock_group", "expiring", "expired", "help"}:
        return None

    return parsed


def _extract_json_object(raw: str) -> dict | None:
    if not raw:
        return None

    candidates = [raw]
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        candidates.insert(0, match.group(0))

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return None


def _fallback_plan(question: str) -> dict:
    norm = _norm(question)
    groups = _groups_from_text(question)

    search_match = re.search(r"\b(buscar|busca|procura|procurar)\s+(.+)", norm)
    if search_match:
        product = search_match.group(2).strip()
        if product:
            return {"intent": "stock_product", "product": product}

    if any(word in norm for word in ("vencido", "vencidos", "vencida", "vencidas")):
        return {"intent": "expired"}

    if any(word in norm for word in ("vence", "vencem", "vencimento", "vencer")):
        days = _extract_days(norm) or 2
        return {"intent": "expiring", "days": days}

    if groups and any(word in norm for word in ("quais", "lista", "listar", "tenho", "inventario", "estoque")):
        return {"intent": "stock_group", "groups": groups}

    if any(word in norm for word in ("hortifruti", "inventario", "estoque", "produtos")):
        return {"intent": "stock_group", "groups": sorted(HORTI_GROUPS)}

    product = _extract_product_guess(question)
    if product:
        return {"intent": "stock_product", "product": product}

    return {"intent": "help"}


def _answer_product_stock(product: str) -> str:
    rows = _horti_rows()
    tokens = [
        token for token in re.split(r"\W+", _norm(product))
        if token.strip()
    ]
    ignored = {
        "quanto", "quanta", "quantos", "quantas", "tem", "tenho", "estoque",
        "buscar", "busca", "procura", "procurar",
        "de", "do", "da", "dos", "das", "o", "a", "os", "as", "hay",
    }
    tokens = [token for token in tokens if token not in ignored]

    if not tokens:
        return "Qual produto você quer consultar? Exemplo: `/ai quanto tenho de tomate?`"

    filtered = [
        row for row in rows
        if all(token in _norm(row[0]) for token in tokens)
    ]

    if not filtered:
        return f"Não encontrei estoque de Hortifruti para '{product}'."

    title = f"Resultado para '{product}'"
    return _format_rows(filtered, title=title, compact=False)


def _answer_group_stock(groups: list[str] | None) -> str:
    selected = [group for group in (groups or []) if group in HORTI_GROUPS]
    if not selected:
        selected = sorted(HORTI_GROUPS)

    rows = [row for row in _horti_rows() if row[3] in selected]
    if not rows:
        labels = ", ".join(GROUP_LABELS[group] for group in selected)
        return f"Não há itens com estoque em {labels}."

    labels = ", ".join(GROUP_LABELS[group] for group in selected)
    return _format_rows(rows, title=f"Estoque Hortifruti - {labels}", compact=True)


def _answer_expiring(days: int = 2) -> str:
    today = date.today()
    end = today + timedelta(days=max(0, min(days, 30)))
    rows = [
        row for row in _horti_rows()
        if row[4] and today <= _only_date(row[4]) <= end
    ]

    if not rows:
        return f"Não há itens de Hortifruti vencendo até {_fmt_fecha(end)}."

    return _format_rows(rows, title=f"Vencimentos até {_fmt_fecha(end)}", compact=False)


def _answer_expired() -> str:
    rows = [
        row for row in obtener_stock_vencido()
        if row[3] in HORTI_GROUPS
    ]

    if not rows:
        return "Não há itens vencidos em Hortifruti com quantidade em estoque."

    return _format_rows(rows, title="Itens vencidos em Hortifruti", compact=False)


def _horti_rows() -> list[tuple]:
    return [
        row for row in obtener_stock_actual()
        if row[3] in HORTI_GROUPS
    ]


def _format_rows(rows: list[tuple], title: str, compact: bool) -> str:
    acc = {}
    for nome, quantidade, unidade, grupo, fecha_producto, contenedor in rows:
        key = (
            grupo,
            (nome or "").strip(),
            (unidade or "").strip(),
            _only_date(fecha_producto),
            (contenedor or "").strip().upper(),
        )
        acc[key] = acc.get(key, 0) + int(quantidade or 0)

    lines = [f"*{title}*"]
    for (grupo, nome, unidade, fecha_producto, contenedor), quantidade in sorted(
        acc.items(),
        key=lambda item: (item[0][3] or date.max, item[0][1].lower(), item[0][0]),
    ):
        group_label = GROUP_LABELS.get(grupo, grupo)
        suffix = f" {unidade}" if unidade else ""
        container = f" ({contenedor})" if grupo == "CON" and contenedor and contenedor != "N/A" else ""
        if compact:
            lines.append(f"• [{group_label}] {nome}: {quantidade}{suffix}")
        else:
            lines.append(
                f"• [{group_label}] {nome}: {quantidade}{suffix}{container} "
                f"({_fmt_fecha(fecha_producto)})"
            )

    return "\n".join(lines)


def _groups_from_text(text: str) -> list[str]:
    norm = _norm(text)
    groups = {
        group for alias, group in GROUP_ALIASES.items()
        if re.search(rf"\b{re.escape(alias)}\b", norm)
    }
    if "ALL" in groups:
        return sorted(HORTI_GROUPS)
    return sorted(groups)


def _extract_product_guess(text: str) -> str:
    norm = _norm(text)
    cleaned = re.sub(
        r"\b(quanto|quanta|quantos|quantas|quais|qual|buscar|busca|procura|procurar|tem|tenho|estoque|stock|saldo|produto|produtos|de|do|da|dos|das|o|a|os|as|hay|ha)\b",
        " ",
        norm,
    )
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def _extract_days(norm_text: str) -> int | None:
    match = re.search(r"(\d+)\s+dias?", norm_text)
    if not match:
        return None
    return int(match.group(1))


def _safe_days(value) -> int:
    if value is None:
        return 2
    if isinstance(value, int):
        return value

    match = re.search(r"\d+", str(value))
    if not match:
        return 2

    return int(match.group(0))


def _norm(value: str) -> str:
    value = (value or "").lower().strip()
    value = unicodedata.normalize("NFD", value)
    return "".join(char for char in value if unicodedata.category(char) != "Mn")


def _only_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value
