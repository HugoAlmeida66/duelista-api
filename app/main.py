"""API da coleção pessoal e dos decks de Yu-Gi-Oh!."""
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Base, Carta, Deck, ItemDeck
from .schemas import (
    CartaAtualizar, CartaCriar, CartaSaida, DeckAtualizar, DeckCriar,
    DeckDetalhe, DeckSaida, ItemEntrada, ItemSaida,
)

load_dotenv()


def create_app(database_url=None, api_key=None, origins=None):
    """Factory permite banco separado nos testes, sem modificar a coleção real."""
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./data/colecao.db")
    api_key = api_key if api_key is not None else os.getenv("API_KEY", "")
    if not api_key or api_key == "SUBSTITUA_POR_UMA_CHAVE_ALEATORIA":
        raise RuntimeError("Configure API_KEY no arquivo .env antes de iniciar.")
    if database_url.startswith("sqlite:///"):
        filename = database_url.removeprefix("sqlite:///")
        if filename != ":memory:":
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {})
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def habilitar_chaves(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA foreign_keys=ON")

    @asynccontextmanager
    async def lifespan(_):
        Base.metadata.create_all(engine)
        yield
        engine.dispose()

    api = FastAPI(title="Duelista — Coleção e Decks", version="1.0.0", lifespan=lifespan,
                  description="Organiza cartas e composições de decks. Não valida regras de torneio nem listas de cartas proibidas.")
    api.state.engine = engine
    cors_origins = origins if origins is not None else os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    api.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in cors_origins if x.strip()],
                       allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                       allow_headers=["Content-Type", "X-API-Key"])
    key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    def autenticar(key: Annotated[str | None, Depends(key_header)]):
        if key is None or not secrets.compare_digest(key.encode(), api_key.encode()):
            raise HTTPException(401, "Chave de acesso ausente ou inválida.", headers={"WWW-Authenticate": "ApiKey"})

    def sessao():
        with Session(engine) as db:
            yield db

    DB = Annotated[Session, Depends(sessao)]
    protecao = [Depends(autenticar)]

    @api.exception_handler(RequestValidationError)
    async def entrada_invalida(_, exc):
        return JSONResponse(status_code=400, content={"detail": "Dados inválidos.", "erros": [
            {"campo": ".".join(map(str, e["loc"])), "mensagem": e["msg"]} for e in exc.errors()]})

    def salvar(db):
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Conflito de dados: nome duplicado ou vínculo inválido.")

    def encontrar(db, classe, identificador):
        obj = db.get(classe, identificador)
        if obj is None:
            raise HTTPException(404, "Recurso não encontrado.")
        return obj

    @api.get("/saude", tags=["Serviço"])
    def saude():
        return {"status": "ok"}

    @api.get("/cartas", response_model=list[CartaSaida], dependencies=protecao, tags=["Cartas"])
    def listar_cartas(db: DB, q: str | None = Query(None, max_length=120),
                      tipo: str | None = None, limite: int = Query(50, ge=1, le=100),
                      deslocamento: int = Query(0, ge=0)):
        stmt = select(Carta)
        if q:
            stmt = stmt.where(Carta.chave_nome.contains(q.strip().casefold(), autoescape=True))
        if tipo:
            if tipo not in ("monstro", "magia", "armadilha"):
                raise HTTPException(400, "Tipo deve ser monstro, magia ou armadilha.")
            stmt = stmt.where(Carta.tipo == tipo)
        return db.scalars(stmt.order_by(Carta.id).offset(deslocamento).limit(limite)).all()

    @api.get("/cartas/{carta_id}", response_model=CartaSaida, dependencies=protecao, tags=["Cartas"])
    def consultar_carta(carta_id: int, db: DB):
        return encontrar(db, Carta, carta_id)

    @api.post("/cartas", response_model=CartaSaida, status_code=201, dependencies=protecao, tags=["Cartas"])
    def criar_carta(dados: CartaCriar, db: DB, response: Response):
        carta = Carta(**dados.model_dump(), chave_nome=dados.nome.casefold())
        db.add(carta); salvar(db); db.refresh(carta)
        response.headers["Location"] = f"/cartas/{carta.id}"
        return carta

    @api.patch("/cartas/{carta_id}", response_model=CartaSaida, dependencies=protecao, tags=["Cartas"])
    def atualizar_carta(carta_id: int, dados: CartaAtualizar, db: DB):
        carta = encontrar(db, Carta, carta_id)
        alteracoes = dados.model_dump(exclude_unset=True)
        if "quantidade" in alteracoes:
            maior_uso = db.scalar(select(func.max(ItemDeck.quantidade)).where(ItemDeck.carta_id == carta_id)) or 0
            if alteracoes["quantidade"] < maior_uso:
                raise HTTPException(409, "A quantidade ficaria menor que a utilizada em um deck.")
        for campo, valor in alteracoes.items():
            setattr(carta, campo, valor)
        if "nome" in alteracoes:
            carta.chave_nome = carta.nome.casefold()
        salvar(db); db.refresh(carta)
        return carta

    @api.delete("/cartas/{carta_id}", status_code=204, dependencies=protecao, tags=["Cartas"])
    def excluir_carta(carta_id: int, db: DB):
        carta = encontrar(db, Carta, carta_id)
        if db.scalar(select(ItemDeck).where(ItemDeck.carta_id == carta_id)):
            raise HTTPException(409, "Remova a carta dos decks antes de excluí-la da coleção.")
        db.delete(carta); salvar(db)
        return Response(status_code=204)

    @api.get("/decks", response_model=list[DeckSaida], dependencies=protecao, tags=["Decks"])
    def listar_decks(db: DB, limite: int = Query(50, ge=1, le=100), deslocamento: int = Query(0, ge=0)):
        return db.scalars(select(Deck).order_by(Deck.id).offset(deslocamento).limit(limite)).all()

    @api.post("/decks", response_model=DeckSaida, status_code=201, dependencies=protecao, tags=["Decks"])
    def criar_deck(dados: DeckCriar, db: DB, response: Response):
        deck = Deck(**dados.model_dump(), chave_nome=dados.nome.casefold())
        db.add(deck); salvar(db); db.refresh(deck)
        response.headers["Location"] = f"/decks/{deck.id}"
        return deck

    @api.get("/decks/{deck_id}", response_model=DeckDetalhe, dependencies=protecao, tags=["Decks"])
    def consultar_deck(deck_id: int, db: DB):
        deck = encontrar(db, Deck, deck_id)
        itens = [ItemSaida(carta=CartaSaida.model_validate(i.carta), quantidade=i.quantidade) for i in deck.itens]
        return DeckDetalhe(id=deck.id, nome=deck.nome, descricao=deck.descricao,
                          itens=itens, total_cartas=sum(i.quantidade for i in itens))

    @api.patch("/decks/{deck_id}", response_model=DeckSaida, dependencies=protecao, tags=["Decks"])
    def atualizar_deck(deck_id: int, dados: DeckAtualizar, db: DB):
        deck = encontrar(db, Deck, deck_id)
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(deck, campo, valor)
        if "nome" in dados.model_fields_set:
            deck.chave_nome = deck.nome.casefold()
        salvar(db); db.refresh(deck)
        return deck

    @api.delete("/decks/{deck_id}", status_code=204, dependencies=protecao, tags=["Decks"])
    def excluir_deck(deck_id: int, db: DB):
        db.delete(encontrar(db, Deck, deck_id)); salvar(db)
        return Response(status_code=204)

    @api.put("/decks/{deck_id}/cartas/{carta_id}", response_model=ItemSaida, dependencies=protecao, tags=["Decks"])
    def definir_item(deck_id: int, carta_id: int, dados: ItemEntrada, db: DB, response: Response):
        encontrar(db, Deck, deck_id)
        carta = encontrar(db, Carta, carta_id)
        if dados.quantidade > carta.quantidade:
            raise HTTPException(409, "O deck não pode usar mais cópias que a coleção possui.")
        item = db.get(ItemDeck, (deck_id, carta_id))
        if item is None:
            item = ItemDeck(deck_id=deck_id, carta_id=carta_id, quantidade=dados.quantidade)
            db.add(item)
            response.status_code = 201
        else:
            item.quantidade = dados.quantidade
        salvar(db)
        return ItemSaida(carta=CartaSaida.model_validate(carta), quantidade=item.quantidade)

    @api.delete("/decks/{deck_id}/cartas/{carta_id}", status_code=204, dependencies=protecao, tags=["Decks"])
    def remover_item(deck_id: int, carta_id: int, db: DB):
        item = encontrar(db, ItemDeck, (deck_id, carta_id))
        db.delete(item); salvar(db)
        return Response(status_code=204)

    gerar_openapi = api.openapi

    def openapi_documentado():
        schema = gerar_openapi()
        for caminho, operacoes in schema['paths'].items():
            for metodo, operacao in operacoes.items():
                respostas = operacao.get('responses', {})
                if '422' in respostas:
                    respostas.pop('422')
                    respostas['400'] = {'description': 'Dados inválidos; consulte detail e erros na resposta JSON.'}
                if operacao.get('security'):
                    respostas['401'] = {'description': 'Chave X-API-Key ausente ou inválida.'}
                    if '{' in caminho:
                        respostas['404'] = {'description': 'Recurso não encontrado.'}
                    if metodo in ('post', 'patch', 'put') or (metodo == 'delete' and caminho.startswith('/cartas/')):
                        respostas['409'] = {'description': 'Conflito de nome, quantidade ou vínculo.'}
                if metodo == 'put':
                    respostas['201'] = {'description': 'Vínculo criado.', 'content': respostas['200']['content']}
        return schema

    api.openapi = openapi_documentado
    return api
