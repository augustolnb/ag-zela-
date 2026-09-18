import sqlite3

ESQUEMA = """
CREATE TABLE IF NOT EXISTS perfil_idoso (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    data_nascimento TEXT NOT NULL,
    condicoes_medicas TEXT NOT NULL,
    contatos_familiares TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medicamento (
    id TEXT PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    nome TEXT NOT NULL,
    dosagem_quantidade REAL NOT NULL,
    dosagem_unidade TEXT NOT NULL,
    horarios TEXT NOT NULL,
    dias_semana TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    bula TEXT
);

CREATE TABLE IF NOT EXISTS confirmacao_medicacao (
    id INTEGER PRIMARY KEY,
    medicamento_id TEXT NOT NULL,
    horario_previsto TEXT NOT NULL,
    horario_confirmado TEXT,
    status TEXT NOT NULL,
    canal TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS compromisso (
    id TEXT PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    titulo TEXT NOT NULL,
    data_hora TEXT NOT NULL,
    local TEXT NOT NULL,
    tipo TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leitura_sensor (
    id INTEGER PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    fonte TEXT NOT NULL,
    tipo TEXT NOT NULL,
    valor REAL NOT NULL,
    unidade TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerta (
    id INTEGER PRIMARY KEY,
    idoso_id TEXT NOT NULL,
    nivel TEXT NOT NULL,
    destinatario TEXT NOT NULL,
    canal TEXT NOT NULL,
    mensagem TEXT NOT NULL,
    status TEXT NOT NULL,
    simulado INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS estado_escalonamento (
    idoso_id TEXT PRIMARY KEY,
    estagio TEXT NOT NULL,
    iniciado_em TEXT
);
"""


def conectar(caminho_db: str = "zela.db") -> sqlite3.Connection:
    conn = sqlite3.connect(caminho_db)
    conn.row_factory = sqlite3.Row
    conn.executescript(ESQUEMA)
    _migrar_coluna_bula(conn)
    return conn


def _migrar_coluna_bula(conn: sqlite3.Connection) -> None:
    colunas = {linha["name"] for linha in conn.execute("PRAGMA table_info(medicamento)")}
    if "bula" not in colunas:
        conn.execute("ALTER TABLE medicamento ADD COLUMN bula TEXT")
        conn.commit()
