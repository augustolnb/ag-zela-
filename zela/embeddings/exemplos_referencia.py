from pydantic import BaseModel

from zela.models.monitoramento import StatusMonitoramento


class ExemploReferencia(BaseModel):
    texto: str
    status: StatusMonitoramento


EXEMPLOS_REFERENCIA: list[ExemploReferencia] = [
    # NORMAL
    ExemploReferencia(texto="Estou bem, acabei de almoçar.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Tudo tranquilo por aqui, só assistindo TV.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Já tomei o remédio, obrigado por perguntar.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Dormi bem essa noite, acordei descansada.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Fui dar uma volta no quintal, está um dia bonito.", status=StatusMonitoramento.NORMAL),
    ExemploReferencia(texto="Estou me sentindo bem hoje, sem dores.", status=StatusMonitoramento.NORMAL),
    # ATENÇÃO
    ExemploReferencia(texto="Estou meio tonta hoje, mas acho que já vai passar.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Tive um pouco de dor de cabeça a tarde toda.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Não dormi muito bem essa noite, me sinto cansada.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Esqueci de tomar o remédio no horário certo.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Estou com um pouco de falta de ar, nada muito forte.", status=StatusMonitoramento.ATENCAO),
    ExemploReferencia(texto="Sinto o coração meio acelerado desde cedo.", status=StatusMonitoramento.ATENCAO),
    # RISCO
    ExemploReferencia(texto="Caí no banheiro e não consigo levantar.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Estou com uma dor muito forte no peito.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Não estou conseguindo respirar direito, socorro.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Estou muito tonta e achei que ia desmaiar agora.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Bati a cabeça forte e estou sangrando.", status=StatusMonitoramento.RISCO),
    ExemploReferencia(texto="Não consigo mexer o braço direito, acho que é AVC.", status=StatusMonitoramento.RISCO),
]
