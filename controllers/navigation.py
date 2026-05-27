import re
from datetime import datetime

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from models.db import (
    get_db_connection,
    insertar_producto,
    obtener_lote_stock_actual,
    obtener_stock_actual,
    obtener_stock_vencido,
    registrar_transferencia,
)
from views.formatters import mensaje_por_fecha_from_tuples


REPLY_MAIN_MENU = [
    ["🥕 HortiFruti", "❄️ Congelados"],
    ["📦 Estoque Seco", "🧪 Estoque Químico"],
    ["🧻 Estoque Descartáveis"],
]

REPLY_HORTI_MENU = [
    ["🥬 Hortaliças", "🍎 Frutas"],
    ["🧀 Laticínios"],
    ["⬅️ Voltar"],
]

REPLY_CONGELADOS_MENU = [
    ["🧊 Picking", "📦 C1"],
    ["📦 C2", "📦 C3"],
    ["⬅️ Voltar"],
]

REPLY_SECTOR_ACTIONS_MENU = [
    ["📦 Ver estoque", "🔍 Buscar"],
    ["➕ Entrada", "➖ Saída"],
    ["↩️ Volta", "🔁 Mover"],
    ["🛠 Ajuste", "📋 Listar descarte"],
    ["🗑 Descarte", "♻️ Devolução"],
    ["⬅️ Voltar"],
]

REPLY_FLOW_MENU = [
    ["✅ Confirmar", "❌ Cancelar"],
]

reply_main_menu_markup = ReplyKeyboardMarkup(
    REPLY_MAIN_MENU,
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Escolha um setor",
)
reply_horti_menu_markup = ReplyKeyboardMarkup(
    REPLY_HORTI_MENU,
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Escolha um grupo",
)
reply_congelados_menu_markup = ReplyKeyboardMarkup(
    REPLY_CONGELADOS_MENU,
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Escolha um contêiner",
)
reply_sector_actions_markup = ReplyKeyboardMarkup(
    REPLY_SECTOR_ACTIONS_MENU,
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Escolha uma ação",
)
reply_flow_markup = ReplyKeyboardMarkup(
    REPLY_FLOW_MENU,
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Confirme ou cancele",
)

REPLY_DIRECT_SECTORS = {
    "📦 Estoque Seco": ("SEC", None),
    "🧪 Estoque Químico": ("QUI", None),
    "🧻 Estoque Descartáveis": ("DES", None),
}

REPLY_HORTI_SECTORS = {
    "🥬 Hortaliças": ("HOR", None),
    "🍎 Frutas": ("FRU", None),
    "🧀 Laticínios": ("LAC", None),
}

REPLY_CONGELADOS_SECTORS = {
    "🧊 Picking": ("CON", "PICK"),
    "📦 C1": ("CON", "C1"),
    "📦 C2": ("CON", "C2"),
    "📦 C3": ("CON", "C3"),
}

REPLY_ACTION_MODES = {
    "🔍 Buscar": "buscar",
    "➕ Entrada": "entrada",
    "➖ Saída": "saida",
    "↩️ Volta": "volta",
    "🔁 Mover": "mover",
    "🛠 Ajuste": "ajuste",
    "📋 Listar descarte": "descarte_vencidos",
    "🗑 Descarte": "descarte",
    "♻️ Devolução": "devolucion",
}

GROUP_LABELS = {
    "HOR": "🥬 Hortaliças",
    "FRU": "🍎 Frutas",
    "LAC": "🧀 Laticínios",
    "CON": "❄️ Congelados",
    "SEC": "📦 Estoque Seco",
    "QUI": "🧪 Estoque Químico",
    "DES": "🧻 Estoque Descartáveis",
}

STATE_KEYS = ("grupo", "contenedor", "modo", "flujo_activo", "pendiente")
VALID_GROUPS = set(GROUP_LABELS)
VALID_CONTAINERS = {"PICK", "C1", "C2", "C3"}
AREAS_VALIDAS = {"alm", "jan", "cof", "kit"}
AJUSTE_CONCEITOS = {"ERRO", "DIVG"}
DB_MODE_BY_FLOW_MODE = {
    "entrada": "entrada",
    "saida": "saida",
    "volta": "volta",
    "ajuste": "ajuste",
    "descarte": "descarte",
    "devolucion": "devolucao",
}
STOCK_CONSUMING_MODES = {"saida", "descarte", "devolucion"}


def _init_user_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.setdefault("grupo", None)
    context.user_data.setdefault("contenedor", None)
    context.user_data.setdefault("modo", None)
    context.user_data.setdefault("flujo_activo", False)
    context.user_data.setdefault("pendiente", [])


def _clear_operation_context(context: ContextTypes.DEFAULT_TYPE) -> None:
    for key in STATE_KEYS:
        context.user_data.pop(key, None)


def _set_sector_context(
    context: ContextTypes.DEFAULT_TYPE,
    grupo: str,
    contenedor: str | None = None,
) -> None:
    _init_user_state(context)
    context.user_data["grupo"] = grupo
    context.user_data["modo"] = None

    if contenedor:
        context.user_data["contenedor"] = contenedor
    else:
        context.user_data["contenedor"] = None


def _context_label(context: ContextTypes.DEFAULT_TYPE) -> str:
    _init_user_state(context)
    grupo = context.user_data.get("grupo")
    contenedor = context.user_data.get("contenedor")

    if not grupo:
        return "sem setor"

    label = GROUP_LABELS.get(grupo, grupo)
    if grupo == "CON" and contenedor:
        return f"{label} / {contenedor}"
    return label


def _parse_fecha(fecha_str: str):
    value = (fecha_str or "").strip().replace("-", "/")
    today = datetime.now()

    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    try:
        day, month = value.split("/")
        return datetime.strptime(f"{day}/{month}/{today.year}", "%d/%m/%Y").date()
    except ValueError:
        return None


def _format_fecha(fecha) -> str:
    if not fecha:
        return "-"

    today = datetime.now().date()
    if fecha.year == today.year:
        return fecha.strftime("%d/%m")
    return fecha.strftime("%d/%m/%Y")


def _operation_prompt_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    _init_user_state(context)
    modo = context.user_data.get("modo")
    base = f"Modo ativo: {modo}\nContexto: {_context_label(context)}"

    if modo == "buscar":
        return f"{base}\nDigite o produto que deseja buscar."

    if modo == "saida":
        return (
            f"{base}\n"
            "Digite um ou vários itens. Cada linha deve terminar com a área de destino.\n"
            "Exemplos:\n"
            "5 kg tomate 30/07 alm\n"
            "3 kg cenoura 31/07 jan"
        )

    if modo == "mover":
        return (
            f"{base}\n"
            "Digite quantidade, unidade, produto, data e destino.\n"
            "Exemplos:\n"
            "5 kg tomate 30/07 FRU\n"
            "5 kg frango 30/07 CON C2\n"
            "35 kg carne 23/11 CON PICK"
        )

    if modo == "ajuste":
        return (
            f"{base}\n"
            "Digite um item por mensagem, incluindo o conceito ERRO ou DIVG.\n"
            "Exemplo: 3 kg tomate 30/07 ERRO"
        )

    if modo == "volta":
        return f"{base}\nDigite um item por mensagem.\nExemplo: 5 kg tomate 30/07 alm"

    if modo in {"entrada", "descarte"}:
        return (
            f"{base}\n"
            "Digite um ou vários itens.\n"
            "Exemplos:\n"
            "20 kg tomate 30/07\n"
            "15 kg cenoura 31/07"
        )

    return f"{base}\nDigite um item por mensagem.\nExemplo: 20 kg tomate 30/07"


def _parse_flow_item(raw_text: str, context: ContextTypes.DEFAULT_TYPE) -> tuple[dict | None, str | None]:
    _init_user_state(context)
    text = (raw_text or "").strip()
    modo = context.user_data.get("modo")
    grupo = context.user_data.get("grupo")
    contenedor = context.user_data.get("contenedor")

    if not text:
        return None, "Digite os dados do item."

    if modo == "buscar":
        return {"nome": text}, None

    if not grupo:
        return None, "Selecione um setor antes de adicionar itens."

    if grupo == "CON" and not contenedor:
        return None, "Selecione um contêiner antes de adicionar itens."

    if "," in text:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        if len(parts) < 3:
            return None, "Formato inválido. Exemplo: 20 kg, tomate, 30/07"
        quantity_unit = parts[0].split()
        if len(quantity_unit) != 2:
            return None, "Informe quantidade e unidade. Exemplo: 20 kg"
        quantity_raw, unidade = quantity_unit
        nome = parts[1]
        fecha_raw = parts[2]
        extras = parts[3:]
    else:
        tokens = text.split()
        if len(tokens) < 4:
            return None, "Formato inválido. Exemplo: 20 kg tomate 30/07"
        quantity_raw, unidade = tokens[0], tokens[1]
        date_index = next(
            (
                index
                for index, token in enumerate(tokens[2:], start=2)
                if re.fullmatch(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?", token)
            ),
            None,
        )
        if date_index is None or date_index == 2:
            return None, "Informe produto e data. Exemplo: 20 kg tomate 30/07"
        nome = " ".join(tokens[2:date_index])
        fecha_raw = tokens[date_index]
        extras = tokens[date_index + 1:]

    try:
        quantidade = int(quantity_raw)
    except ValueError:
        return None, "Quantidade inválida."

    if quantidade <= 0:
        return None, "A quantidade deve ser maior que zero."

    if not _parse_fecha(fecha_raw):
        return None, "Data inválida. Use dd/mm, dd/mm/aa ou dd/mm/aaaa."

    item = {
        "nome": nome.lower().strip(),
        "quantidade": quantidade,
        "unidade": unidade.lower().strip(),
        "fecha": fecha_raw,
        "grupo": grupo,
        "contenedor": contenedor,
    }

    if modo in {"saida", "volta"}:
        if not extras:
            return None, "Informe a área: alm, jan, cof ou kit."
        concepto = extras[0].lower()
        if concepto not in AREAS_VALIDAS:
            return None, "Área inválida. Use: alm, jan, cof ou kit."
        item["concepto"] = concepto

    if modo == "ajuste":
        if not extras:
            return None, "Informe o conceito do ajuste: ERRO ou DIVG."
        concepto = extras[0].upper()
        if concepto not in AJUSTE_CONCEITOS:
            return None, "Conceito inválido. Use apenas ERRO ou DIVG."
        item["concepto"] = concepto

    if modo == "mover":
        if not extras:
            return None, "Informe o grupo de destino. Exemplo: FRU ou CON C2."

        normalized_extras = [extra.upper() for extra in extras]
        if normalized_extras[0] == grupo:
            if grupo == "CON" and len(normalized_extras) > 1 and normalized_extras[1] == contenedor:
                normalized_extras = normalized_extras[2:]
            elif grupo != "CON":
                normalized_extras = normalized_extras[1:]

        if not normalized_extras:
            return None, "Informe o grupo de destino. Exemplo: FRU ou CON C2."

        destino_grupo = normalized_extras[0]
        destino_contenedor = normalized_extras[1] if len(normalized_extras) > 1 else None
        if destino_grupo not in VALID_GROUPS:
            return None, "Grupo de destino inválido. Use HOR, FRU, LAC, CON, SEC, QUI ou DES."
        if destino_grupo == "CON":
            if destino_contenedor not in VALID_CONTAINERS:
                return None, "Informe o contêiner de destino: PICK, C1, C2 ou C3."
        else:
            destino_contenedor = None

        if destino_grupo == grupo and destino_contenedor == contenedor:
            return None, "A origem e o destino devem ser diferentes."

        if destino_grupo == grupo and grupo != "CON":
            return None, "O grupo de origem e o grupo de destino devem ser diferentes."

        item["destino_grupo"] = destino_grupo
        item["destino_contenedor"] = destino_contenedor

    return item, None


def _split_flow_entries(raw_text: str, context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    if context.user_data.get("modo") not in {"entrada", "saida", "descarte"}:
        return [(raw_text or "").strip()]

    return [
        item.strip()
        for item in re.split(r"[;\n]+", raw_text or "")
        if item.strip()
    ]


def _parse_flow_items(raw_text: str, context: ContextTypes.DEFAULT_TYPE) -> tuple[list[dict], str | None]:
    entries = _split_flow_entries(raw_text, context)
    if not entries:
        return [], "Digite os dados do item."

    items = []
    for index, entry in enumerate(entries, start=1):
        item, error = _parse_flow_item(entry, context)
        if error:
            return [], f"Item {index}: {error}"
        items.append(item)

    return items, None


def _movement_signature(modo: str, item: dict) -> tuple:
    return (
        modo,
        item.get("nome"),
        item.get("unidade"),
        item.get("fecha"),
        item.get("grupo"),
        item.get("contenedor"),
        item.get("concepto"),
        item.get("destino_grupo"),
        item.get("destino_contenedor"),
    )


def _normalize_pending_items(modo: str, items: list[dict]) -> list[dict]:
    normalized = []
    index_by_signature = {}

    for item in items:
        signature = _movement_signature(modo, item)
        if signature in index_by_signature:
            normalized[index_by_signature[signature]]["quantidade"] += item["quantidade"]
            continue

        index_by_signature[signature] = len(normalized)
        normalized.append(dict(item))

    return normalized


def _stock_totals_by_lot(items: list[dict]) -> dict:
    totals = {}

    for item in items:
        fecha_producto = _parse_fecha(item["fecha"])
        key = (
            item["nome"],
            item["grupo"],
            fecha_producto,
            item.get("contenedor"),
            item["unidade"],
        )
        totals[key] = totals.get(key, 0) + item["quantidade"]

    return totals


def _validate_stock_consuming_items(items: list[dict], action_label: str) -> str | None:
    totals = _stock_totals_by_lot(items)

    for (nome, grupo, fecha_producto, contenedor, unidade), quantidade_total in totals.items():
        if not fecha_producto:
            return f"Data inválida para {nome}."

        lote = obtener_lote_stock_actual(
            nome,
            grupo,
            fecha_producto,
            contenedor,
            unidade=unidade,
        )

        if not lote:
            extra = f" ({contenedor})" if grupo == "CON" and contenedor else ""
            return (
                f"❌ {nome}{extra} não está no estoque para "
                f"{_format_fecha(fecha_producto)} com unidade {unidade}."
            )

        _, quantidade_lote, unidade_lote, _, _, cont_lote = lote
        unidade_lote = (unidade_lote or "").lower()

        if unidade_lote and unidade != unidade_lote:
            return (
                f"❌ Unidade diferente para {nome}.\n"
                f"Estoque: {unidade_lote} | Informado: {unidade}"
            )

        if int(quantidade_lote or 0) < quantidade_total:
            extra = f" ({cont_lote})" if grupo == "CON" and cont_lote and cont_lote != "N/A" else ""
            return (
                f"⚠️ Estoque insuficiente para {nome}{extra} ({_format_fecha(fecha_producto)}).\n"
                f"Estoque disponível: {quantidade_lote}{unidade_lote or unidade}\n"
                f"{action_label} solicitada: {quantidade_total}{unidade}"
            )

    return None


def _validate_ajuste_items(items: list[dict]) -> str | None:
    for item in items:
        fecha_producto = _parse_fecha(item["fecha"])
        if not fecha_producto:
            return f"Data inválida para {item['nome']}."

        lote = obtener_lote_stock_actual(
            item["nome"],
            item["grupo"],
            fecha_producto,
            item.get("contenedor"),
            unidade=item["unidade"],
        )
        if not lote:
            return (
                "❌ Nenhum lote encontrado para ajuste.\n"
                f"Verifique {item['nome']}, data, grupo e contêiner."
            )

        _, quantidade_lote, unidade_lote, _, _, cont_lote = lote
        unidade_lote = (unidade_lote or "").lower()

        if unidade_lote and item["unidade"] != unidade_lote:
            return (
                f"❌ Unidade diferente para {item['nome']}.\n"
                f"Estoque: {unidade_lote} | Informado: {item['unidade']}"
            )

        quantidade_lote = int(quantidade_lote or 0)
        if item.get("concepto") == "DIVG" and item["quantidade"] > quantidade_lote:
            extra = f" ({cont_lote})" if item["grupo"] == "CON" and cont_lote and cont_lote != "N/A" else ""
            return (
                f"❌ Ajuste DIVG não permitido para {item['nome']}{extra}.\n"
                f"Estoque do lote: {quantidade_lote}{unidade_lote or item['unidade']}\n"
                f"Ajuste solicitado: {item['quantidade']}{item['unidade']}"
            )

    return None


def _validate_mover_items(items: list[dict]) -> str | None:
    totals = _stock_totals_by_lot(items)

    for item in items:
        if item.get("destino_grupo") == item.get("grupo") and item.get("destino_contenedor") == item.get("contenedor"):
            return "❌ A origem e o destino devem ser diferentes."

        if item.get("destino_grupo") == item.get("grupo") and item.get("grupo") != "CON":
            return "❌ O grupo de origem e o grupo de destino devem ser diferentes."

    for (nome, grupo, fecha_producto, contenedor, unidade), quantidade_total in totals.items():
        if not fecha_producto:
            return f"Data inválida para {nome}."

        lote = obtener_lote_stock_actual(
            nome,
            grupo,
            fecha_producto,
            contenedor,
            unidade=unidade,
        )
        if not lote:
            return (
                "❌ Lote não encontrado para mover.\n"
                "Verifique produto, data, unidade, grupo de origem e contêiner."
            )

        _, quantidade_lote, unidade_lote, _, _, cont_lote = lote
        unidade_lote = (unidade_lote or "").lower()

        if unidade_lote and unidade != unidade_lote:
            return (
                f"❌ Unidade diferente para {nome}.\n"
                f"Estoque: {unidade_lote} | Informado: {unidade}"
            )

        if int(quantidade_lote or 0) < quantidade_total:
            extra = f" ({cont_lote})" if grupo == "CON" and cont_lote and cont_lote != "N/A" else ""
            return (
                f"❌ Estoque insuficiente para mover {nome}{extra}.\n"
                f"Estoque do lote: {quantidade_lote}{unidade_lote or unidade}\n"
                f"Quantidade solicitada: {quantidade_total}{unidade}"
            )

    return None


def _validate_flow_stock(context: ContextTypes.DEFAULT_TYPE, new_items: list[dict] | None = None) -> str | None:
    modo = context.user_data.get("modo")
    if modo not in STOCK_CONSUMING_MODES | {"ajuste", "mover"}:
        return None

    items = list(context.user_data.get("pendiente", []))
    if new_items:
        items.extend(new_items)
    items = _normalize_pending_items(modo, items)

    if modo in STOCK_CONSUMING_MODES:
        return _validate_stock_consuming_items(items, "Quantidade")

    if modo == "ajuste":
        return _validate_ajuste_items(items)

    if modo == "mover":
        return _validate_mover_items(items)

    return None


def _db_concept_for_item(modo: str, item: dict) -> str | None:
    if modo == "entrada":
        return "fornecedor"
    return item.get("concepto")


def _validate_duplicate_movements(modo: str, items: list[dict]) -> str | None:
    if modo == "mover":
        return None

    tipo = DB_MODE_BY_FLOW_MODE.get(modo)
    if not tipo:
        return None

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        for item in items:
            fecha_producto = _parse_fecha(item["fecha"])
            contenedor = item.get("contenedor") if item.get("grupo") == "CON" else "N/A"
            concepto = _db_concept_for_item(modo, item)

            cursor.execute(
                """
                SELECT 1
                FROM movimientos
                WHERE nombre = %s
                  AND tipo = %s
                  AND fecha_producto = %s
                  AND unidade = %s
                  AND grupo = %s
                  AND contenedor = %s
                  AND concepto IS NOT DISTINCT FROM %s
                LIMIT 1;
                """,
                (
                    item["nome"],
                    tipo,
                    fecha_producto,
                    item["unidade"],
                    item["grupo"],
                    contenedor,
                    concepto,
                ),
            )

            if cursor.fetchone():
                extra = f" ({contenedor})" if item["grupo"] == "CON" else ""
                return (
                    f"⚠️ Movimento duplicado detectado para {item['nome']}{extra} "
                    f"({_format_fecha(fecha_producto)}).\n"
                    "Revise a operação antes de confirmar."
                )
    except Exception as exc:
        return f"⚠️ Erro ao validar duplicados: {exc}"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return None


def _format_pending_review(context: ContextTypes.DEFAULT_TYPE) -> str:
    _init_user_state(context)
    pending = context.user_data.get("pendiente", [])
    if not pending:
        return "📋 Nenhum item adicionado ainda."

    lines = ["📋 Revisar operação", ""]
    for index, item in enumerate(pending, start=1):
        if context.user_data.get("modo") == "buscar":
            lines.append(f"{index}. {item['nome']}")
            continue

        extra = ""
        if item.get("concepto"):
            extra = f" • {item['concepto']}"
        if item.get("destino_grupo"):
            destino = GROUP_LABELS.get(item["destino_grupo"], item["destino_grupo"])
            if item.get("destino_contenedor"):
                destino = f"{destino} / {item['destino_contenedor']}"
            extra = f" • destino: {destino}"
        lines.append(
            f"{index}. {item['nome']} — {item['quantidade']}{item['unidade']} "
            f"({item['fecha']}){extra}"
        )

    lines.append("")
    lines.append("Toque em Confirmar para gravar ou Cancelar para descartar.")
    return "\n".join(lines)


async def _send_reply_menu_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_markup: ReplyKeyboardMarkup,
) -> None:
    await update.effective_chat.send_message(text, reply_markup=reply_markup)


async def _send_operation_reply_prompt(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await update.effective_chat.send_message(
        _operation_prompt_text(context),
        reply_markup=reply_flow_markup,
    )


async def _send_stock_for_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _init_user_state(context)
    grupo = context.user_data.get("grupo")
    contenedor = context.user_data.get("contenedor")

    if not grupo:
        await update.message.reply_text(
            "Selecione um setor antes de consultar o estoque.",
            reply_markup=reply_main_menu_markup,
        )
        return

    try:
        rows = obtener_stock_actual(grupo=grupo)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Erro ao consultar estoque: {exc}")
        return

    if contenedor:
        rows = [
            row
            for row in rows
            if (row[5] or "").strip().upper() == contenedor
        ]

    if not rows:
        await update.message.reply_text(
            f"Setor ativo: {_context_label(context)}\n\n"
            f"📦 Nenhum item registrado no estoque para {_context_label(context)}.",
            reply_markup=reply_sector_actions_markup,
        )
        return

    await update.message.reply_text(
        f"Setor ativo: {_context_label(context)}\n\n"
        f"{mensaje_por_fecha_from_tuples(rows, titulo_grupo=_context_label(context))}",
        parse_mode="Markdown",
        reply_markup=reply_sector_actions_markup,
    )


async def _send_search_for_context(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str) -> None:
    _init_user_state(context)
    grupo = context.user_data.get("grupo")
    contenedor = context.user_data.get("contenedor")
    query_norm = (query or "").strip().lower()

    if not query_norm:
        await update.message.reply_text("Digite o nome do produto para buscar.", reply_markup=reply_flow_markup)
        return

    try:
        rows = obtener_stock_actual(grupo=grupo) if grupo else obtener_stock_actual()
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Erro ao buscar estoque: {exc}")
        return

    if contenedor:
        rows = [
            row
            for row in rows
            if (row[5] or "").strip().upper() == contenedor
        ]

    rows = [
        row
        for row in rows
        if query_norm in (row[0] or "").lower()
    ]

    if not rows:
        scope = _context_label(context) if grupo else "todos os setores"
        await update.message.reply_text(
            f"🔍 Nenhum item encontrado para '{query}' em {scope}.",
            reply_markup=reply_sector_actions_markup,
        )
        context.user_data["modo"] = None
        context.user_data["flujo_activo"] = False
        context.user_data["pendiente"] = []
        return

    title = f"Busca: {query}"
    if grupo:
        title = f"{title} — {_context_label(context)}"

    await update.message.reply_text(
        mensaje_por_fecha_from_tuples(rows, titulo_grupo=title),
        parse_mode="Markdown",
        reply_markup=reply_sector_actions_markup,
    )
    context.user_data["modo"] = None
    context.user_data["flujo_activo"] = False
    context.user_data["pendiente"] = []


async def _send_expired_discard_list_for_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _init_user_state(context)
    grupo = context.user_data.get("grupo")
    contenedor = context.user_data.get("contenedor")

    if not grupo:
        await update.message.reply_text(
            "Selecione um setor antes de listar itens para descarte.",
            reply_markup=reply_main_menu_markup,
        )
        return

    try:
        rows = obtener_stock_vencido(grupo=grupo)
    except Exception as exc:
        await update.message.reply_text(f"⚠️ Erro ao listar itens vencidos: {exc}")
        return

    if contenedor:
        rows = [
            row
            for row in rows
            if (row[5] or "").strip().upper() == contenedor
        ]

    if not rows:
        await update.message.reply_text(
            f"✅ Não há itens vencidos com quantidade em estoque para {_context_label(context)}.",
            reply_markup=reply_sector_actions_markup,
        )
        return

    today = datetime.now().date()
    lines = [f"⚠️ *Itens vencidos para descarte — {_context_label(context)}*", ""]

    for nome, quantidade, unidade, grupo_item, fecha, cont in rows:
        extra = f" ({cont})" if grupo_item == "CON" and cont and cont != "N/A" else ""
        dias = (today - fecha).days
        lines.append(
            f"• {nome}: {quantidade}{unidade}{extra}\n"
            f"  Vencido há {dias} dia(s) ({_format_fecha(fecha)})"
        )

    lines.append("")
    lines.append("Este botão apenas lista os itens. Para registrar descarte, use o botão Descarte.")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=reply_sector_actions_markup,
    )


async def _confirm_pending_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _init_user_state(context)
    modo = context.user_data.get("modo")
    pending = context.user_data.get("pendiente", [])

    if not context.user_data.get("flujo_activo"):
        await update.message.reply_text("Não há operação em andamento.", reply_markup=reply_sector_actions_markup)
        return

    if not pending:
        await update.message.reply_text("Adicione pelo menos um item antes de confirmar.", reply_markup=reply_flow_markup)
        return

    if modo == "buscar":
        await _send_search_for_context(update, context, pending[0]["nome"])
        return

    try:
        pending = _normalize_pending_items(modo, pending)
        context.user_data["pendiente"] = pending

        stock_error = _validate_flow_stock(context)
        if stock_error:
            await update.message.reply_text(
                stock_error,
                reply_markup=reply_flow_markup,
            )
            return

        duplicate_error = _validate_duplicate_movements(modo, pending)
        if duplicate_error:
            await update.message.reply_text(
                duplicate_error,
                reply_markup=reply_flow_markup,
            )
            return

        for item in pending:
            fecha_producto = _parse_fecha(item["fecha"])
            quantidade = item["quantidade"]
            concepto = item.get("concepto")

            if modo == "mover":
                registrar_transferencia(
                    nombre=item["nome"],
                    cantidad=item["quantidade"],
                    fecha_producto=fecha_producto,
                    unidade=item["unidade"],
                    grupo_origen=item["grupo"],
                    grupo_destino=item["destino_grupo"],
                    contenedor_origen=item.get("contenedor"),
                    contenedor_destino=item.get("destino_contenedor"),
                )
                continue

            if modo == "entrada":
                concepto = "fornecedor"

            if modo == "ajuste" and item.get("concepto") == "ERRO":
                lote = obtener_lote_stock_actual(
                    item["nome"],
                    item["grupo"],
                    fecha_producto,
                    item.get("contenedor"),
                    unidade=item["unidade"],
                )
                quantidade = int(lote[1])

            insertar_producto(
                item["nome"],
                quantidade,
                DB_MODE_BY_FLOW_MODE[modo],
                fecha_producto,
                item["unidade"],
                item["grupo"],
                item.get("contenedor"),
                concepto=concepto,
            )

        total = len(pending)
        _clear_operation_context(context)
        await update.message.reply_text(
            f"✅ Operação confirmada. {total} item(ns) gravado(s).",
            reply_markup=reply_main_menu_markup,
        )
    except Exception as exc:
        await update.message.reply_text(
            f"⚠️ Erro ao confirmar operação: {exc}\n"
            "A operação foi mantida em andamento para revisão ou cancelamento.",
            reply_markup=reply_flow_markup,
        )


async def _cancel_pending_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _clear_operation_context(context)
    await update.message.reply_text(
        "Operação cancelada. Nenhum item foi gravado.",
        reply_markup=reply_main_menu_markup,
    )


async def start_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_operation_context(context)
    await _send_reply_menu_message(
        update,
        context,
        "Olá! Selecione um setor:",
        reply_main_menu_markup,
    )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_operation_context(context)
    await _send_reply_menu_message(
        update,
        context,
        "Selecione um setor:",
        reply_main_menu_markup,
    )


async def show_reply_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _clear_operation_context(context)
    await _send_reply_menu_message(
        update,
        context,
        "Teclado inferior ativo. Selecione um setor:",
        reply_main_menu_markup,
    )


async def handle_reply_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if context.user_data.get("flujo_activo"):
        await update.message.reply_text(
            "⚠️ Você já possui uma operação em andamento.\n"
            "Confirme ou cancele antes de iniciar outra.",
            reply_markup=reply_flow_markup,
        )
        return

    if text == "🥕 HortiFruti":
        _clear_operation_context(context)
        await _send_reply_menu_message(
            update,
            context,
            "Selecione o grupo de HortiFruti:",
            reply_horti_menu_markup,
        )
        return

    if text == "❄️ Congelados":
        _clear_operation_context(context)
        await _send_reply_menu_message(
            update,
            context,
            "Selecione o contêiner de congelados:",
            reply_congelados_menu_markup,
        )
        return

    if text == "📋 Requisições":
        await _send_reply_menu_message(
            update,
            context,
            "📋 Requisições ainda não estão configuradas neste fluxo.",
            reply_main_menu_markup,
        )
        return

    sector = REPLY_DIRECT_SECTORS.get(text)
    if sector:
        grupo, contenedor = sector
        _set_sector_context(context, grupo, contenedor)
        await _send_stock_for_context(update, context)


async def handle_reply_horti_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if context.user_data.get("flujo_activo"):
        await update.message.reply_text(
            "⚠️ Você já possui uma operação em andamento.\n"
            "Confirme ou cancele antes de iniciar outra.",
            reply_markup=reply_flow_markup,
        )
        return

    if text == "⬅️ Voltar":
        _clear_operation_context(context)
        await _send_reply_menu_message(update, context, "Selecione um setor:", reply_main_menu_markup)
        return

    sector = REPLY_HORTI_SECTORS.get(text)
    if not sector:
        return

    grupo, contenedor = sector
    _set_sector_context(context, grupo, contenedor)
    await _send_stock_for_context(update, context)


async def handle_reply_congelados_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if context.user_data.get("flujo_activo"):
        await update.message.reply_text(
            "⚠️ Você já possui uma operação em andamento.\n"
            "Confirme ou cancele antes de iniciar outra.",
            reply_markup=reply_flow_markup,
        )
        return

    if text == "⬅️ Voltar":
        _clear_operation_context(context)
        await _send_reply_menu_message(update, context, "Selecione um setor:", reply_main_menu_markup)
        return

    sector = REPLY_CONGELADOS_SECTORS.get(text)
    if not sector:
        return

    grupo, contenedor = sector
    _set_sector_context(context, grupo, contenedor)
    await _send_stock_for_context(update, context)


async def handle_reply_sector_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    _init_user_state(context)

    if text == "✅ Confirmar":
        await _confirm_pending_operation(update, context)
        return

    if text == "❌ Cancelar":
        await _cancel_pending_operation(update, context)
        return

    if context.user_data.get("flujo_activo"):
        await update.message.reply_text(
            "⚠️ Você já possui uma operação em andamento.\n"
            "Confirme ou cancele antes de iniciar outra.",
            reply_markup=reply_flow_markup,
        )
        return

    if text == "⬅️ Voltar":
        grupo = context.user_data.get("grupo")
        if grupo in {"HOR", "FRU", "LAC"}:
            context.user_data["modo"] = None
            context.user_data["grupo"] = None
            context.user_data["contenedor"] = None
            await _send_reply_menu_message(update, context, "Selecione o grupo de HortiFruti:", reply_horti_menu_markup)
            return

        if grupo == "CON":
            context.user_data["modo"] = None
            context.user_data["grupo"] = None
            context.user_data["contenedor"] = None
            await _send_reply_menu_message(update, context, "Selecione o contêiner de congelados:", reply_congelados_menu_markup)
            return

        _clear_operation_context(context)
        await _send_reply_menu_message(update, context, "Selecione um setor:", reply_main_menu_markup)
        return

    if text == "📦 Ver estoque":
        await _send_stock_for_context(update, context)
        return

    modo = REPLY_ACTION_MODES.get(text)
    if not modo:
        return

    if modo == "descarte_vencidos":
        await _send_expired_discard_list_for_context(update, context)
        return

    if not context.user_data.get("grupo") and modo != "buscar":
        await update.message.reply_text("Selecione um setor antes de iniciar a operação.")
        return

    context.user_data["modo"] = modo
    context.user_data["flujo_activo"] = True
    context.user_data["pendiente"] = []
    await _send_operation_reply_prompt(update, context)


async def handle_flow_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _init_user_state(context)

    if not context.user_data.get("flujo_activo"):
        return

    if context.user_data.get("modo") == "buscar":
        await _send_search_for_context(update, context, update.message.text)
        return

    items, error = _parse_flow_items(update.message.text, context)
    if error:
        await update.message.reply_text(error, reply_markup=reply_flow_markup)
        return

    stock_error = _validate_flow_stock(context, new_items=items)
    if stock_error:
        await update.message.reply_text(stock_error, reply_markup=reply_flow_markup)
        return

    context.user_data["pendiente"] = _normalize_pending_items(
        context.user_data.get("modo"),
        [*context.user_data["pendiente"], *items],
    )
    await update.message.reply_text(
        _format_pending_review(context),
        reply_markup=reply_flow_markup,
    )
