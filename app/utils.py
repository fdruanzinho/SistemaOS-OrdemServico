from datetime import datetime


def gerar_numero(model, campo_numero, prefixo):
    """Gera o próximo número sequencial no formato PREFIXO-0001."""
    ultimo = model.query.order_by(model.id.desc()).first()
    proximo = (ultimo.id + 1) if ultimo else 1
    return f"{prefixo}-{proximo:04d}"


def formatar_moeda(valor):
    try:
        valor = float(valor or 0)
    except (TypeError, ValueError):
        valor = 0
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_data(data, com_hora=False):
    if not data:
        return "-"
    fmt = "%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y"
    return data.strftime(fmt)


def parse_float(valor, padrao=0.0):
    if valor is None or valor == "":
        return padrao
    try:
        if isinstance(valor, str):
            valor = valor.replace(".", "").replace(",", ".") if "," in valor else valor
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Validação de documentos e textos
# ---------------------------------------------------------------------------

import calendar
import re


def so_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def validar_cpf(valor):
    """Valida CPF pelos dígitos verificadores (exatamente 11 dígitos)."""
    cpf = so_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def validar_cnpj(valor):
    """Valida CNPJ pelos dígitos verificadores (exatamente 14 dígitos)."""
    cnpj = so_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(pos))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[pos]):
            return False
    return True


def formatar_cpf(valor):
    d = so_digitos(valor)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return valor


def formatar_cnpj(valor):
    d = so_digitos(valor)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return valor


def formatar_telefone(valor):
    d = so_digitos(valor)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return valor


def formatar_cep(valor):
    d = so_digitos(valor)
    if len(d) == 8:
        return f"{d[:5]}-{d[5:]}"
    return valor


def texto_limpo(valor):
    """Remove espaços e transforma vazio / 'None' em None (evita gravar 'None' no banco)."""
    if valor is None:
        return None
    valor = str(valor).strip()
    if valor == "" or valor.lower() in ("none", "null"):
        return None
    return valor


def somar_meses(data, meses):
    """Soma meses a uma data mantendo o dia (ajusta para o fim do mês quando necessário)."""
    mes = data.month - 1 + meses
    ano = data.year + mes // 12
    mes = mes % 12 + 1
    dia = min(data.day, calendar.monthrange(ano, mes)[1])
    return data.replace(year=ano, month=mes, day=dia)
