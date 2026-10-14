import pytest
from fastapi.testclient import TestClient
from app.main import create_app

CHAVE = "chave-exclusiva-do-banco-temporario-dos-testes"
HEADERS = {"X-API-Key": CHAVE}
CARTA = {"nome": "Mago Negro", "tipo": "monstro", "quantidade": 3}


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'teste.db'}", CHAVE)
    with TestClient(app) as c:
        c.headers.update(HEADERS)
        yield c


def test_crud_e_filtros(client):
    r = client.post('/cartas', json=CARTA)
    assert r.status_code == 201 and r.headers['location'] == '/cartas/1'
    assert client.get('/cartas/1').json()['nome'] == CARTA['nome']
    assert len(client.get('/cartas?q=MAGO&tipo=monstro').json()) == 1
    assert client.get('/cartas?q=dragão').json() == []
    assert client.patch('/cartas/1', json={'quantidade': 2}).json()['quantidade'] == 2
    assert client.get('/cartas/1').json()['tipo'] == 'monstro'
    r = client.delete('/cartas/1')
    assert r.status_code == 204 and not r.content
    assert client.get('/cartas/1').status_code == 404


@pytest.mark.parametrize('body', [
    {**CARTA, 'nome': '  '}, {**CARTA, 'quantidade': 0},
    {**CARTA, 'quantidade': True}, {**CARTA, 'quantidade': '3'},
    {**CARTA, 'tipo': 'desconhecido'}, {**CARTA, 'campo_extra': 1},
])
def test_validacao_criacao(client, body):
    assert client.post('/cartas', json=body).status_code == 400
    assert client.get('/cartas').json() == []


@pytest.mark.parametrize('body', [{}, {'nome': None}, {'quantidade': -1}])
def test_patch_invalido_nao_altera_banco(client, body):
    client.post('/cartas', json=CARTA)
    assert client.patch('/cartas/1', json=body).status_code == 400
    assert client.get('/cartas/1').json()['quantidade'] == 3


def test_duplicidade_e_rollback(client):
    client.post('/cartas', json=CARTA)
    assert client.post('/cartas', json={**CARTA, 'nome': ' mago negro '}).status_code == 409
    assert client.post('/cartas', json={**CARTA, 'nome': 'Dragão Branco'}).status_code == 201
    assert client.patch('/cartas/2', json={'nome': 'Mago Negro'}).status_code == 409
    assert client.get('/cartas/2').json()['nome'] == 'Dragão Branco'


def test_autenticacao(client):
    client.headers.clear()
    assert client.get('/cartas').status_code == 401
    assert client.get('/cartas', headers={'X-API-Key': 'errada'}).status_code == 401
    assert client.get('/cartas', headers=HEADERS).status_code == 200
    assert client.get('/saude').status_code == 200


def test_cors(client):
    h = {'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'PATCH',
         'Access-Control-Request-Headers': 'X-API-Key,Content-Type'}
    r = client.options('/cartas/1', headers=h)
    assert r.status_code == 200
    assert r.headers['access-control-allow-origin'] == h['Origin']
    h['Origin'] = 'https://origem-nao-permitida.example'
    r = client.options('/cartas/1', headers=h)
    assert r.status_code == 400 and 'access-control-allow-origin' not in r.headers


def test_relacionamento_decks_e_limites(client):
    client.post('/cartas', json=CARTA)
    assert client.post('/decks', json={'nome': 'Magos'}).status_code == 201
    assert client.put('/decks/1/cartas/1', json={'quantidade': 2}).status_code == 201
    for _ in range(2):
        assert client.put('/decks/1/cartas/1', json={'quantidade': 2}).status_code == 200
    detalhe = client.get('/decks/1').json()
    assert len(detalhe['itens']) == 1 and detalhe['total_cartas'] == 2
    assert client.put('/decks/1/cartas/1', json={'quantidade': 4}).status_code == 409
    assert client.patch('/cartas/1', json={'quantidade': 1}).status_code == 409
    assert client.delete('/cartas/1').status_code == 409
    assert client.patch('/decks/1', json={'descricao': 'Deck de teste'}).status_code == 200
    assert client.get('/decks').json()[0]['descricao'] == 'Deck de teste'
    assert client.delete('/decks/1').status_code == 204
    assert client.delete('/cartas/1').status_code == 204


def test_remocao_item_e_recurso_inexistente(client):
    client.post('/cartas', json=CARTA)
    client.post('/decks', json={'nome': 'Magos'})
    assert client.put('/decks/1/cartas/999', json={'quantidade': 1}).status_code == 404
    client.put('/decks/1/cartas/1', json={'quantidade': 1})
    assert client.delete('/decks/1/cartas/1').status_code == 204
    assert client.delete('/decks/1/cartas/1').status_code == 404
    assert client.get('/decks/1').json()['total_cartas'] == 0


def test_persistencia_apos_reinicio(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistencia.db'}"
    with TestClient(create_app(url, CHAVE)) as c:
        assert c.post('/cartas', json=CARTA, headers=HEADERS).status_code == 201
    with TestClient(create_app(url, CHAVE)) as c:
        assert c.get('/cartas/1', headers=HEADERS).json()['nome'] == CARTA['nome']


def test_sem_chave_nao_inicia():
    with pytest.raises(RuntimeError):
        create_app(api_key='')


def test_documentacao_e_parametros(client):
    assert client.get('/docs').status_code == 200
    doc = client.get('/openapi.json').json()
    assert doc['paths']['/cartas']['get']['security'] == [{'APIKeyHeader': []}]
    assert '400' in doc['paths']['/cartas']['post']['responses']
    assert '422' not in doc['paths']['/cartas']['post']['responses']
    assert '401' in doc['paths']['/cartas']['get']['responses']
    assert '201' in doc['paths']['/decks/{deck_id}/cartas/{carta_id}']['put']['responses']
    assert client.get('/cartas?limite=101').status_code == 400
    assert client.get('/cartas?tipo=invalido').status_code == 400
    assert client.post('/cartas', content='{').status_code == 400
