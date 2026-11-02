import re
import unicodedata
from dataclasses import dataclass
from enum import Enum


class CategoriaMensagem(str, Enum):
    PEDIDO_AJUDA = "pedido_ajuda"
    SINTOMA_GRAVE = "sintoma_grave"
    CANCELAMENTO_ESTOU_BEM = "cancelamento_estou_bem"
    CANCELAMENTO_RECUSA = "cancelamento_recusa"
    NENHUM = "nenhum"


@dataclass(frozen=True)
class ClassificacaoMensagem:
    categoria: CategoriaMensagem
    sintomas: tuple[str, ...] = ()


# Listas determinísticas de propósito: o aviso à família não pode depender do
# Gemini estar disponível. Falso positivo é aceitável (a pessoa pode cancelar
# em 60 s); falso negativo é o erro caro.
_SINTOMAS = {
    "coração acelerado": r"coracao\s+(\w+\s+)?(acelerad\w*|disparad\w*)|palpitac\w*",
    "tontura": r"tontura\w*|tont[oa]s?|zonz[oa]s?",
    "desmaio": r"desmai\w*",
    "dor no peito": r"dor\s+(\w+\s+)?no\s+peito|peito\s+doendo|aperto\s+no\s+peito",
    "falta de ar": r"falta\s+de\s+ar|sem\s+ar|nao\s+consigo\s+respirar|dificuldade\s+(para|pra|de)\s+respirar",
    "formigamento": r"formig\w*",
    "fala enrolada": r"fala\s+enrolad\w*|enrolando\s+a\s+fala",
    "queda": r"cai|caiu|cair|tombo|queda",
    "sangramento": r"sangr\w*",
    "confusão": r"confus[oa]s?|confusao",
    "muita dor": r"muita\s+dor|dor\s+(muito\s+)?forte",
    "mal-estar": r"passando\s+(\w+\s+)?mal|sentindo\s+(\w+\s+)?mal|(estou|to|tou)\s+(\w+\s+)?mal|mal\s+estar|nao\s+estou\s+bem|nao\s+to\s+bem",
    "pressão alterada": r"pressao\s+(\w+\s+)?(alta|baixa|subiu|caiu)",
}

_NEGACAO = r"\b(nao|sem)\s+((estou|to|tou|tenho|senti|sinto|tive|estava|com|nenhuma?)\s+)*$"

_VERBO_AVISO = (
    r"avise|avisa|avisar|avisem|chame|chama|chamar|chamem|ligue|liga|ligar|liguem|"
    r"contate|contata|contatar|contacte|acione|aciona|acionar"
)
_RECUSA = re.compile(
    rf"\bnao\s+(precisa\s+(de\s+)?)?(me\s+)?({_VERBO_AVISO}|incomode|incomoda|incomodar)\b"
    r"|\bnao\s+preciso\s+de\s+ajuda\b|\bcancela\b|\bcancele\b|\bcancelar\b"
)
_PEDIDO = re.compile(
    rf"\b({_VERBO_AVISO})\s+(\w+\s+){{0,4}}?"
    r"(familia|familiar(es)?|filh[oa]s?|net[oa]s?|espos[oa]|marido|mulher|irm(a|ao)s?|parentes?|alguem|medico|ambulancia|samu|socorro)\b"
    r"|\bsocorro\b|\bpreciso\s+de\s+ajuda\b|\bme\s+ajud[ae]\b|\bprecisando\s+de\s+ajuda\b"
)
# Pergunta genérica sobre remédio não é relato: "a losartana pode causar tontura?"
# não pode avisar a família. Qualquer marca de primeira pessoa mantém o relato.
_PERGUNTA_SOBRE_REMEDIO = re.compile(
    r"\b(pode\s+causar|pode\s+dar|causa|da|efeitos?\s+colaterais?|reac(ao|oes)|bula|contraindic\w*|para\s+que\s+serve)\b"
)
_PRIMEIRA_PESSOA = re.compile(
    r"\b(estou|to|tou|tenho|tive|senti|sinto|sentindo|tomei|me|meu|minha|comigo|eu|cai|acabei|passando)\b"
)
# Mensagem inteira: "estou bem mal" e "não estou bem" não podem cancelar.
_ESTOU_BEM = re.compile(
    r"(sim\s+)?(eu\s+)?((estou|to|tou|ta|esta)\s+)?(tudo\s+)?(bem|certo|ok|otimo|otima|melhor)"
    r"(\s+(sim|agora|obrigad[oa]))*|sim|ja\s+passou|passou(\s+agora)?"
)


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sem_acento.lower()).split())


def _encontrar_sintomas(texto: str) -> tuple[str, ...]:
    encontrados = []
    for nome, padrao in _SINTOMAS.items():
        for ocorrencia in re.finditer(rf"\b({padrao})\b", texto):
            if not re.search(_NEGACAO, texto[: ocorrencia.start()]):
                encontrados.append(nome)
                break
    return tuple(encontrados)


def _eh_pergunta_sobre_remedio(texto: str, normalizado: str) -> bool:
    return (
        "?" in texto
        and _PERGUNTA_SOBRE_REMEDIO.search(normalizado) is not None
        and _PRIMEIRA_PESSOA.search(normalizado) is None
    )


def classificar_mensagem(texto: str) -> ClassificacaoMensagem:
    normalizado = _normalizar(texto)
    sintomas = _encontrar_sintomas(normalizado)
    if sintomas and _eh_pergunta_sobre_remedio(texto, normalizado):
        sintomas = ()

    # A recusa vem antes do pedido: "não chame minha filha" contém "chame minha filha".
    if _RECUSA.search(normalizado):
        if sintomas:
            return ClassificacaoMensagem(CategoriaMensagem.SINTOMA_GRAVE, sintomas)
        return ClassificacaoMensagem(CategoriaMensagem.CANCELAMENTO_RECUSA)
    if _PEDIDO.search(normalizado):
        return ClassificacaoMensagem(CategoriaMensagem.PEDIDO_AJUDA, sintomas)
    if sintomas:
        return ClassificacaoMensagem(CategoriaMensagem.SINTOMA_GRAVE, sintomas)
    if _ESTOU_BEM.fullmatch(normalizado):
        return ClassificacaoMensagem(CategoriaMensagem.CANCELAMENTO_ESTOU_BEM)
    return ClassificacaoMensagem(CategoriaMensagem.NENHUM)
