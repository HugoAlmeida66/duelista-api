"""Reproduz os exemplos HTTP em um banco temporário, sem alterar a coleção."""
import json
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app

records = []
key = secrets.token_urlsafe(32)

with tempfile.TemporaryDirectory() as tmp:
    url = f"sqlite:///{Path(tmp) / 'evidencias.db'}"
    with TestClient(create_app(url, key)) as client:
        def registrar(rotulo, metodo, rota, esperado, dados=None, autorizado=True, headers=None):
            h = {'X-API-Key': key} if autorizado else {}
            h.update(headers or {})
            r = client.request(metodo, rota, json=dados, headers=h)
            assert r.status_code == esperado, (rotulo, r.status_code, r.text)
            records.append({'rotulo': rotulo, 'metodo': metodo, 'rota': rota,
                            'entrada': dados, 'autenticado': autorizado,
                            'headers_entrada': headers or {}, 'status': r.status_code,
                            'headers_resposta': {k:v for k,v in r.headers.items() if k in
                                                 ['location','access-control-allow-origin','access-control-allow-methods','access-control-allow-headers']},
                            'resposta': (r.json() if 'application/json' in r.headers.get('content-type','') else r.text) if r.content else None})
            return r

        carta = {'nome':'Mago Negro','tipo':'monstro','quantidade':3}
        registrar('sem_chave','GET','/cartas',401,autorizado=False)
        registrar('post','POST','/cartas',201,carta)
        registrar('lista','GET','/cartas',200)
        registrar('consulta','GET','/cartas/1',200)
        registrar('filtro','GET','/cartas?q=mago&tipo=monstro',200)
        registrar('patch','PATCH','/cartas/1',200,{'quantidade':2})
        registrar('invalido','POST','/cartas',400,{**carta,'quantidade':0})
        registrar('duplicado','POST','/cartas',409,carta)
        registrar('nao_encontrado','GET','/cartas/999',404)
        registrar('deck','POST','/decks',201,{'nome':'Magos','descricao':'Composição de estudo'})
        registrar('item','PUT','/decks/1/cartas/1',201,{'quantidade':2})
        registrar('put_repetido','PUT','/decks/1/cartas/1',200,{'quantidade':2})
        registrar('deck_detalhe','GET','/decks/1',200)
        registrar('estoque','PUT','/decks/1/cartas/1',409,{'quantidade':3})
        registrar('exclusao_vinculada','DELETE','/cartas/1',409)
        registrar('cors','OPTIONS','/cartas',200,autorizado=False,headers={
            'Origin':'http://localhost:5173','Access-Control-Request-Method':'GET',
            'Access-Control-Request-Headers':'X-API-Key'})
        registrar('cors_negado','OPTIONS','/cartas',400,autorizado=False,headers={
            'Origin':'https://origem-nao-permitida.example','Access-Control-Request-Method':'GET'})
        registrar('remover_item','DELETE','/decks/1/cartas/1',204)
        registrar('delete','DELETE','/cartas/1',204)
        registrar('apos_exclusao','GET','/cartas/1',404)
        registrar('nova_carta','POST','/cartas',201,{'nome':'Dragão Branco de Olhos Azuis','tipo':'monstro','quantidade':1})
    with TestClient(create_app(url,key)) as client:
        r=client.get('/cartas',headers={'X-API-Key':key})
        assert r.status_code==200 and r.json()[0]['nome']=='Dragão Branco de Olhos Azuis'
        records.append({'rotulo':'persistencia','metodo':'GET','rota':'/cartas','entrada':None,
                        'autenticado':True,'status':r.status_code,'headers_resposta':{},'resposta':r.json()})

out=Path(__file__).parent/'evidencias';out.mkdir(exist_ok=True)
data={'executado_em':datetime.now(timezone.utc).isoformat(),'ferramenta':'FastAPI TestClient / httpx',
      'banco':'SQLite temporário em arquivo; aplicação encerrada e recriada no teste de persistência',
      'requisicoes':records}
(out/'requisicoes.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
lines=[]
for r in records:
    lines += [f"{r['rotulo']}: {r['metodo']} {r['rota']}",
              'X-API-Key: [ocultada]' if r['autenticado'] else 'Sem chave de autenticação',
              'Entrada: '+json.dumps(r['entrada'],ensure_ascii=False),
              f"HTTP {r['status']}",'Resposta: '+json.dumps(r['resposta'],ensure_ascii=False),'']
(out/'requisicoes.txt').write_text('\n'.join(lines),encoding='utf-8')
print(f'{len(records)} requisições verificadas, incluindo persistência após reinício.')
