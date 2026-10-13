# Duelista — Coleção e Decks de Yu-Gi-Oh!

Projeto acadêmico de Arquitetura e Desenvolvimento de APIs.
Aluno: HUGO DA SILVA ALMEIDA — RU 5412058.

API para registrar uma coleção pessoal de cartas e salvar composições de decks.
As cartas são cadastradas manualmente. Não depende de serviços externos e não
valida regras de torneio, limite oficial de cópias, banlist, Main/Extra/Side Deck
ou autenticidade das cartas. Não é um serviço oficial da Konami.

## Tecnologias

Python 3.12, FastAPI, SQLAlchemy ORM, SQLite, Uvicorn, Pydantic e pytest.
FastAPI documenta os endpoints em OpenAPI/Swagger. SQLite facilita a execução
local; o arquivo persiste depois que o servidor é encerrado. SQLAlchemy mapeia
classes e associações para tabelas, sem montar SQL a partir de entrada do usuário.

## Instalação e execução

Instale Python 3.12. Na pasta do projeto, execute:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copie a chave aleatória gerada para `API_KEY` no `.env`. Não publique esse arquivo.
O servidor se recusa a iniciar sem chave ou com o marcador do exemplo.
No Linux/macOS, use `.venv/bin/python` e `cp .env.example .env`.

```powershell
.venv\Scripts\python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

- Serviço: http://127.0.0.1:8000/saude
- Swagger: http://127.0.0.1:8000/docs
- Contrato OpenAPI: http://127.0.0.1:8000/openapi.json

As tabelas são criadas automaticamente na inicialização pelo
`Base.metadata.create_all`. O arquivo padrão é `data/colecao.db`; não é necessário
instalar um servidor de banco. Esse procedimento cria a estrutura inicial,
mas não migra alterações posteriores do modelo. Não apague o banco para
atualizar uma instalação com dados reais; migrações são uma melhoria futura.

## Autenticação e CORS

Em `/docs`, clique em **Authorize**, informe a chave do seu `.env` e confirme.
Todas as rotas de cartas, decks e itens exigem `X-API-Key`. Uma chave ausente ou
incorreta retorna 401. `/saude`, `/docs` e `/openapi.json` são públicos.
A chave representa uma coleção única: não há usuários nem isolamento por conta.
Em uma publicação real, use HTTPS e adicione usuários, permissões e limitação de requisições.

`CORS_ORIGINS` aceita origens separadas por vírgula. Por padrão, permite apenas
`http://localhost:5173`, pensando em um futuro cliente local. Métodos permitidos:
GET, POST, PATCH, PUT e DELETE. Cabeçalhos: Content-Type e X-API-Key.
Credenciais por cookies não são liberadas. CORS controla leitura por navegadores;
não substitui autenticação. O Swagger servido pela própria API usa a mesma origem.

## Recursos e regras

`Carta` registra nome, tipo (monstro/magia/armadilha), quantidade de 1 a 999,
idioma, conservação (nova/boa/usada/danificada) e observações.
Uma linha agrupa cópias de uma carta com a mesma descrição. Nomes duplicados,
ignorando caixa e espaços nas pontas, retornam 409. A versão inicial não separa
edições distintas de uma mesma carta.

`Deck` contém nome e descrição. `ItemDeck` liga deck e carta, com quantidade.
Sua chave primária é composta por deck_id e carta_id, impedindo itens duplicados.
Cada deck pode usar até a quantidade disponível da carta. Decks são planos de
composição e podem reutilizar as mesmas cópias entre si, sem reservar estoque.
Reduzir a coleção abaixo da quantidade de um deck retorna 409. Uma carta em uso
não pode ser excluída. Excluir um deck remove seus vínculos, preservando a coleção.

## Endpoints

| Método | Rota | Resultado principal |
|---|---|---|
| GET | /saude | 200 |
| GET | /cartas | 200; filtros q/tipo, limite e deslocamento |
| GET | /cartas/{id} | 200 ou 404 |
| POST | /cartas | 201 e Location; 400 ou 409 |
| PATCH | /cartas/{id} | 200; 400, 404 ou 409 |
| DELETE | /cartas/{id} | 204 sem corpo; 404 ou 409 |
| GET | /decks | 200; paginação |
| GET | /decks/{id} | 200 com itens e total; 404 |
| POST | /decks | 201; 400 ou 409 |
| PATCH | /decks/{id} | 200; 400, 404 ou 409 |
| DELETE | /decks/{id} | 204; 404 |
| PUT | /decks/{id}/cartas/{carta_id} | 201 ao criar; 200 ao substituir; 400, 404 ou 409 |
| DELETE | /decks/{id}/cartas/{carta_id} | 204; 404 |

Rotas protegidas também podem retornar 401. PATCH atualiza somente os campos
enviados. PUT define toda a quantidade de um item: repetir o pedido não cria
cópias adicionais. Dados inválidos são convertidos para 400, com detalhes dos
campos; conflitos retornam 409. Objetos inexistentes retornam 404.

Exemplo no PowerShell, usando sua chave local sem escrevê-la no repositório:

```powershell
$chaveDuelista = Read-Host 'Chave configurada no .env'
$cabecalhosDuelista = @{ 'X-API-Key' = $chaveDuelista }
$corpoDuelista = @{ nome='Mago Negro'; tipo='monstro'; quantidade=3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/cartas -Headers $cabecalhosDuelista -ContentType 'application/json; charset=utf-8' -Body ([System.Text.Encoding]::UTF8.GetBytes($corpoDuelista))
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/cartas?q=Mago' -Headers $cabecalhosDuelista
```

## Testes

```powershell
.venv\Scripts\python -m pytest -q
```

Os testes usam arquivos SQLite temporários e uma chave exclusiva de teste,
sem acessar seu `.env` ou a coleção real. Verificam CRUD, filtros, validação,
autenticação, CORS, duplicidade/rollback, relação entre cartas e decks,
idempotência de PUT, exclusão em cascata e persistência após reinicialização.
As evidências de requisições estão em `evidencias/`.

## Organização

```text
app/main.py       rotas, autenticação, CORS, sessão e regras de negócio
app/models.py     mapeamento ORM de Carta, Deck e ItemDeck
app/schemas.py    contratos e validação de entrada/saída
tests/            testes automatizados
evidencias/       registros reais de execução
.env.example      configuração sem credenciais reais
```

## Referências

- https://fastapi.tiangolo.com/tutorial/
- https://fastapi.tiangolo.com/tutorial/cors/
- https://docs.sqlalchemy.org/en/21/orm/quickstart.html
- https://docs.python.org/3/library/sqlite3.html
