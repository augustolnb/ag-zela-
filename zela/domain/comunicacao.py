from zela.domain.compromisso_lembretes import TipoLembreteCompromisso
from zela.models.comunicacao import MensagemEntrada
from zela.models.rotina import Compromisso, Medicamento

PALAVRAS_CONFIRMACAO = {"sim", "ok", "certo", "feito", "tomei"}
PALAVRAS_NEGACAO = {"não", "nao", "esqueci"}


def formatar_lembrete(medicamento: Medicamento) -> str:
    return (
        f"Olá! Hora de tomar {medicamento.nome} "
        f"({medicamento.dosagem.quantidade} {medicamento.dosagem.unidade}). "
        "Responda 'tomei' quando fizer isso, tá bem?"
    )


def formatar_lembrete_compromisso(compromisso: Compromisso, tipo_lembrete: str) -> str:
    data = compromisso.data_hora.strftime("%d/%m às %H:%M")
    detalhes = f"{compromisso.titulo} ({data}, {compromisso.local})"
    if tipo_lembrete == TipoLembreteCompromisso.INSTANTANEO.value:
        return f"Olá! Você tem um compromisso agendado: {detalhes}."
    if tipo_lembrete == TipoLembreteCompromisso.H24.value:
        return f"Olá! Lembrete: amanhã você tem {detalhes}."
    if tipo_lembrete == TipoLembreteCompromisso.MANHA.value:
        return f"Bom dia! Hoje você tem {detalhes}."
    if tipo_lembrete == TipoLembreteCompromisso.H1.value:
        return f"Olá! Daqui a pouco, às {compromisso.data_hora.strftime('%H:%M')}, você tem {detalhes}."
    if tipo_lembrete == TipoLembreteCompromisso.CANCELAMENTO.value:
        return f"Olá! Informamos que o compromisso {detalhes} foi cancelado."
    raise ValueError(f"tipo de lembrete desconhecido: {tipo_lembrete}")


def interpretar_resposta(mensagem: MensagemEntrada) -> bool | None:
    texto = (mensagem.transcricao or mensagem.conteudo_bruto).strip().lower()
    palavras_do_texto = set(texto.replace(",", "").split())
    if palavras_do_texto & PALAVRAS_NEGACAO:
        return False
    if palavras_do_texto & PALAVRAS_CONFIRMACAO:
        return True
    return None
