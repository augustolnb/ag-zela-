from zela.models.comunicacao import MensagemEntrada
from zela.models.rotina import Medicamento

PALAVRAS_CONFIRMACAO = {"sim", "ok", "certo", "feito", "tomei"}
PALAVRAS_NEGACAO = {"não", "nao", "esqueci"}


def formatar_lembrete(medicamento: Medicamento) -> str:
    return (
        f"Olá! Hora de tomar {medicamento.nome} "
        f"({medicamento.dosagem.quantidade} {medicamento.dosagem.unidade}). "
        "Responda 'tomei' quando fizer isso, tá bem?"
    )


def interpretar_resposta(mensagem: MensagemEntrada) -> bool | None:
    texto = (mensagem.transcricao or mensagem.conteudo_bruto).strip().lower()
    palavras_do_texto = set(texto.replace(",", "").split())
    if palavras_do_texto & PALAVRAS_NEGACAO:
        return False
    if palavras_do_texto & PALAVRAS_CONFIRMACAO:
        return True
    return None
