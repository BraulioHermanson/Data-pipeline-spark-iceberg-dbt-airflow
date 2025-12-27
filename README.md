# Data-pipeline-spark-iceberg-dbt-airflow
<img width="2816" height="1536" alt="pipeline-iceberg-dbt" src="https://github.com/user-attachments/assets/9e7467cd-8386-4e42-bd0c-0dcae242cc54" />

[PT-BR]
# Pipeline de Dados Bitcoin - PySpark + Iceberg + dbt + Airflow

## 📋 Visão Geral

Este projeto implementa um pipeline de dados completo para extração, transformação e análise de preços do Bitcoin utilizando tecnologias modernas de Data Engineering.

## 🏗️ Arquitetura
```
┌─────────────────────────────────────────────────────────────────┐
│                        AIRFLOW DAG                               │
│                  bitcoin_analytics_pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌───────────┐    ┌───────────┐         │
│  │ extract_bitcoin  │───▶│  dbt_run  │───▶│ dbt_test  │         │
│  │     _prices      │    │           │    │           │         │
│  └──────────────────┘    └───────────┘    └───────────┘         │
│          │                     │                │                │
└──────────┼─────────────────────┼────────────────┼────────────────┘
           ▼                     ▼                ▼
   ┌───────────────┐     ┌─────────────┐   ┌─────────────┐
   │  PySpark +    │     │    dbt      │   │    dbt      │
   │   Iceberg     │     │   models    │   │   tests     │
   └───────────────┘     └─────────────┘   └─────────────┘
           │                     │
           ▼                     ▼
   ┌───────────────────────────────────────┐
   │           Apache Iceberg              │
   │  ┌─────────────────────────────────┐  │
   │  │ raw.bitcoin_prices (raw data)   │  │
   │  │ raw.stg_bitcoin_prices (staging)│  │
   │  │ raw.fct_bitcoin_daily (marts)   │  │
   │  └─────────────────────────────────┘  │
   └───────────────────────────────────────┘
                     │
                     ▼
           ┌─────────────────┐
           │  MinIO (S3)     │
           │  warehouse/     │
           └─────────────────┘
```

## 🛠️ Stack Tecnológica

| Componente | Versão | Função |
|------------|--------|--------|
| **Apache Airflow** | 2.10.3 | Orquestração de pipelines |
| **Apache Spark** | 3.5.1 | Processamento distribuído |
| **Apache Iceberg** | 1.4.3 | Formato de tabela (Data Lakehouse) |
| **dbt-spark** | 1.9.0 | Transformações SQL |
| **MinIO** | Latest | Object Storage (compatível S3) |
| **Docker** | - | Containerização |

## 📁 Estrutura do Projeto
```
~/Folder/iceberg-dbt-project/
├── docker-compose.yml          # Definição dos containers
├── spark/
│   ├── Dockerfile              # Imagem customizada do Spark
│   ├── spark-defaults.conf     # Configurações do Spark
│   └── entrypoint.sh           # Script de inicialização
├── scripts/
│   ├── extract_bitcoin_prices.py   # Script de extração PySpark
│   └── dbt/
│       └── bitcoin_analytics/      # Projeto dbt
│           ├── dbt_project.yml
│           ├── profiles.yml
│           └── models/
│               ├── staging/
│               │   └── stg_bitcoin_prices.sql
│               └── marts/
│                   └── fct_bitcoin_daily.sql
├── dags/
│   └── bitcoin_pipeline_dag.py     # DAG do Airflow
└── README.md
```

---

## 📚 Folder de Aprendizado

### 1. Configuração Inicial do Ambiente

#### 1.1 Docker Compose com Múltiplos Serviços

O primeiro desafio foi configurar todos os serviços para trabalharem juntos:

- **MinIO**: Object storage compatível com S3
- **Iceberg REST Catalog**: Gerenciamento de metadados das tabelas
- **Spark Master/Worker**: Processamento distribuído
- **Spark Thrift Server**: Interface SQL para conexões externas

**Aprendizado**: Cada serviço precisa estar na mesma rede Docker (`iceberg-net`) para se comunicarem pelo nome do container.

#### 1.2 Conflito de Portas

O Spark Master usa porta 8080 por padrão, que conflitava com o Airflow.

**Solução**: Remapear a porta do Spark Master para 8082:
```yaml
ports:
  - "8082:8080"  # Spark UI em localhost:8082
```

### 2. Extração de Dados com PySpark

#### 2.1 Configuração do Spark com Iceberg

O Spark precisa de JARs específicos e configurações para trabalhar com Iceberg:
```python
SparkSession.builder \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.iceberg.type", "rest") \
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181")
```

**Aprendizado**: O Iceberg não é apenas um formato de arquivo - é uma camada de gerenciamento que adiciona ACID transactions, time travel e schema evolution sobre arquivos Parquet.

#### 2.2 Estrutura Física vs Lógica
```
Iceberg Table
├── data/*.parquet     ← Dados reais (formato Parquet)
└── metadata/*.json    ← Controle do Iceberg (snapshots, schema)
```

### 3. Transformações com dbt

#### 3.1 Tentativa 1: dbt no WSL (venv)

**Problema**: Instalação global do pip polui o sistema.

**Solução**: Criar uma virtual environment:
```bash
cd ~/Folder/iceberg-dbt-project
python -m venv venv
source venv/bin/activate
pip install 'dbt-spark[PyHive]'
```

**Aprendizado**: Sempre usar venv para projetos Python - isola dependências e evita conflitos.

#### 3.2 Iceberg Não Suporta Views

**Problema**: Ao rodar `dbt run`, erro:
```
Catalog iceberg does not support views
```

**Solução**: Mudar materialização de `view` para `table`:
```sql
{{ config(materialized='table') }}
```

**Aprendizado**: Nem todas as features SQL são suportadas por todos os catálogos. Iceberg foca em tabelas ACID, não views.

#### 3.3 Conexão dbt → Spark Thrift

**Problema**: dbt não conseguia conectar ao Spark Thrift Server.

**Erro**: `Could not connect to any of [('127.0.0.1', 10000)]`

**Causa**: O schema `default` não existia no Iceberg.

**Solução**: Configurar o profiles.yml corretamente:
```yaml
bitcoin_analytics:
  target: dev
  outputs:
    dev:
      type: spark
      method: thrift
      host: spark-thrift
      port: 10000
      schema: iceberg.raw  # Formato: catalog.namespace
```

### 4. Orquestração com Airflow

#### 4.1 Tentativa 1: BashOperator Simples

**Problema**: Airflow roda em container Docker separado, não tem acesso ao `docker` CLI.

**Erro**: `Cannot connect to the Docker daemon`

**Solução**: Montar o Docker socket no container do Airflow:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

#### 4.2 Tentativa 2: Permissão do Docker Socket

**Problema**: Mesmo com socket montado, erro de permissão.

**Erro**: `permission denied while trying to connect to the Docker daemon socket`

**Solução**: Ajustar permissões do socket:
```bash
sudo chmod 666 /var/run/docker.sock
```

**Aprendizado**: Essa permissão volta ao padrão após reiniciar o Docker/WSL.

#### 4.3 Tentativa 3: dbt no Container do Airflow

**Problema**: Airflow não conseguia executar o dbt da venv do WSL.

**Erro**: `/home/user/.../venv/bin/dbt: cannot execute: required file not found`

**Causa**: A venv foi criada no WSL Linux, não funciona dentro do container Docker (sistemas diferentes).

**Tentativa de Solução**: Instalar dbt dentro do container do Airflow:
```bash
docker exec -u airflow airflow_b-airflow-worker-1 pip install 'dbt-spark[PyHive]'
```

**Resultado**: Instalou, mas ainda tinha problemas de rede entre containers.

#### 4.4 Solução Final: dbt no Container Spark

**Abordagem**: Instalar dbt no mesmo container que executa o Spark, eliminando problemas de rede.
```bash
docker exec -u 0 spark-master pip install 'dbt-spark[PyHive]'
```

**DAG Final**:
```python
# Task 1: Extrair dados via PySpark
extract = BashOperator(
    task_id='extract_bitcoin_prices',
    bash_command='docker exec spark-master spark-submit /opt/spark/scripts/extract_bitcoin_prices.py',
)

# Task 2: Transformar via dbt (executado dentro do spark-master)
transform = BashOperator(
    task_id='dbt_run',
    bash_command='docker exec spark-master dbt run --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics',
)
```

**Aprendizado**: Às vezes a solução mais simples é colocar as ferramentas no mesmo lugar, evitando complexidade de rede entre containers.

### 5. Conexão de Redes Docker

Para que o Airflow conseguisse executar `docker exec` nos containers do Spark:
```bash
# Conectar containers do Airflow à rede do Iceberg
docker network connect iceberg-net airflow_b-airflow-worker-1
docker network connect iceberg-net airflow_b-airflow-scheduler-1
```

**Aprendizado**: Containers em redes Docker diferentes não se enxergam pelo nome. Use `docker network connect` para unir redes.

---

## 🔧 Comandos Úteis

### Inicialização
```bash
# Iniciar stack Iceberg/Spark
cd ~/Folder/iceberg-dbt-project
docker compose up -d

# Iniciar Airflow
cd ~/Folder/airflow_b
docker compose up -d

# Permissão do Docker socket (necessário após reiniciar WSL/Docker)
sudo chmod 666 /var/run/docker.sock
```

**Por que o chmod?** O Docker socket pertence ao grupo `docker`. Dentro dos containers, o usuário não está nesse grupo, então precisa de permissão aberta.

### Execução Manual do Pipeline
```bash
# 1. Extrair dados das APIs
docker exec spark-master spark-submit /opt/spark/scripts/extract_bitcoin_prices.py

# 2. Rodar transformações dbt
docker exec spark-master dbt run --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# 3. Rodar testes dbt
docker exec spark-master dbt test --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics
```

### Consultas SQL
```bash
# Abrir shell SQL interativo
docker exec -it spark-master spark-sql

# Consultas diretas
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.bitcoin_prices LIMIT 10"
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.fct_bitcoin_daily"

# Ver histórico de snapshots (time travel)
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.bitcoin_prices.snapshots"
```

**Por que usar spark-sql?** É a forma mais direta de consultar tabelas Iceberg sem precisar de ferramentas externas.

### Debugging
```bash
# Ver logs dos containers
docker logs spark-master
docker logs spark-thrift
docker logs iceberg-rest

# Verificar status dos containers
docker ps | grep -E "spark|minio|iceberg|airflow"

# Verificar redes
docker network inspect iceberg-net

# Testar conectividade entre containers
docker exec spark-master curl -v telnet://spark-thrift:10000
```

### dbt
```bash
# Debug de conexão
docker exec spark-master dbt debug --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# Rodar modelo específico
docker exec spark-master dbt run --select stg_bitcoin_prices --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# Ver documentação gerada
docker exec spark-master dbt docs generate --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics
```

---

## 🎯 Lições Aprendidas

### 1. Isolamento de Ambientes
- **Virtual environments** são essenciais para projetos Python
- **Containers Docker** isolam serviços mas criam desafios de rede
- Considere onde cada ferramenta vai rodar antes de instalar

### 2. Rede Docker
- Containers na mesma rede se comunicam pelo **nome do container**
- Containers em redes diferentes precisam de `docker network connect`
- `localhost` dentro de um container não é o mesmo que `localhost` no host

### 3. Compatibilidade de Ferramentas
- Nem todas as features SQL funcionam em todos os sistemas
- Iceberg não suporta **views**, apenas **tables**
- Versões de bibliotecas importam (dbt-spark precisa de PyHive para Thrift)

### 4. Debugging em Containers
- Sempre teste comandos manualmente antes de automatizar
- Use `docker exec` para entrar nos containers e debugar
- Logs são seus amigos: `docker logs <container>`

### 5. Persistência e Restart
- Use `restart: always` no docker-compose para serviços que devem iniciar automaticamente
- Permissões de socket voltam ao padrão após restart
- Dados em volumes Docker persistem entre restarts

---

## 📊 Modelos dbt

### stg_bitcoin_prices (Staging)
```sql
{{ config(materialized='table') }}

SELECT
    source as data_source,
    symbol as crypto_symbol,
    COALESCE(price_usd, 0) as price_usd,
    COALESCE(price_eur, 0) as price_eur,
    COALESCE(price_brl, 0) as price_brl,
    COALESCE(market_cap_usd, 0) as market_cap_usd,
    COALESCE(volume_24h_usd, 0) as volume_24h_usd,
    COALESCE(change_24h_pct, 0) as price_change_24h_pct,
    extracted_at,
    DATE(extracted_at) as extraction_date
FROM iceberg.raw.bitcoin_prices
```

### fct_bitcoin_daily (Marts)
```sql
{{ config(materialized='table') }}

SELECT
    extraction_date,
    data_source,
    crypto_symbol,
    MIN(price_usd) as min_price_usd,
    MAX(price_usd) as max_price_usd,
    AVG(price_usd) as avg_price_usd,
    COUNT(*) as records
FROM {{ ref('stg_bitcoin_prices') }}
GROUP BY extraction_date, data_source, crypto_symbol
```

---

<img width="2816" height="1536" alt="containers" src="https://github.com/user-attachments/assets/3e0ba3f3-8804-4413-87f7-f5a52b8b94c5" />

---

## 📝 Próximos Passos

- [ ] Adicionar mais fontes de dados (outras criptomoedas)
- [ ] Implementar alertas no Airflow
- [ ] Criar dashboards com os dados transformados
- [ ] Implementar CI/CD para os modelos dbt
- [ ] Configurar backup automático do MinIO

---

[EN]

📋 Overview
This project implements a complete data pipeline for extracting, transforming, and analyzing Bitcoin prices using modern Data Engineering technologies.

🏗️ Architecture
```
┌─────────────────────────────────────────────────────────────────┐
│                        AIRFLOW DAG                               │
│                  bitcoin_analytics_pipeline                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐    ┌───────────┐    ┌───────────┐         │
│  │ extract_bitcoin  │───▶│  dbt_run  │───▶│ dbt_test  │         │
│  │     _prices      │    │           │    │           │         │
│  └──────────────────┘    └───────────┘    └───────────┘         │
│          │                     │                │                │
└──────────┼─────────────────────┼────────────────┼────────────────┘
           ▼                     ▼                ▼
   ┌───────────────┐     ┌─────────────┐   ┌─────────────┐
   │  PySpark +    │     │    dbt      │   │    dbt      │
   │   Iceberg     │     │   models    │   │   tests     │
   └───────────────┘     └─────────────┘   └─────────────┘
           │                     │
           ▼                     ▼
   ┌───────────────────────────────────────┐
   │           Apache Iceberg              │
   │  ┌─────────────────────────────────┐  │
   │  │ raw.bitcoin_prices (raw data)   │  │
   │  │ raw.stg_bitcoin_prices (staging)│  │
   │  │ raw.fct_bitcoin_daily (marts)   │  │
   │  └─────────────────────────────────┘  │
   └───────────────────────────────────────┘
                     │
                     ▼
           ┌─────────────────┐
           │  MinIO (S3)     │
           │  warehouse/     │
           └─────────────────┘
```
## 🛠️ Stack Tecnológica

| Componente | Versão | Função |
|------------|--------|--------|
| **Apache Airflow** | 2.10.3 | Pipeline orchestration |
| **Apache Spark** | 3.5.1 | Distributed processing |
| **Apache Iceberg** | 1.4.3 | Table format (Data Lakehouse) |
| **dbt-spark** | 1.9.0 | SQL Transformations |
| **MinIO** | Latest | Object Storage (S3 compatible) |
| **Docker** | - | Containerization |

## 📁 Project Structure
```
~/Folder/iceberg-dbt-project/
├── docker-compose.yml          # Definição dos containers
├── spark/
│   ├── Dockerfile              # Imagem customizada do Spark
│   ├── spark-defaults.conf     # Configurações do Spark
│   └── entrypoint.sh           # Script de inicialização
├── scripts/
│   ├── extract_bitcoin_prices.py   # Script de extração PySpark
│   └── dbt/
│       └── bitcoin_analytics/      # Projeto dbt
│           ├── dbt_project.yml
│           ├── profiles.yml
│           └── models/
│               ├── staging/
│               │   └── stg_bitcoin_prices.sql
│               └── marts/
│                   └── fct_bitcoin_daily.sql
├── dags/
│   └── bitcoin_pipeline_dag.py     # DAG do Airflow
└── README.md
```

---

## 📚 Learning Log

### 1. Initial Environment Setup

#### 1.1 Docker Compose with Multiple Services

The first challenge was configuring all services to work together:

- **MinIO**: S3-compatible object storage
- **Iceberg REST Catalog**: Management of table metadata.
- **Spark Master/Worker**: Distributed processing.
- **Spark Thrift Server**: SQL interface for external connections.

**Key Learning**: Each service must be on the same Docker network (iceberg-net) to communicate via container names.

#### 1.2 Port conflict

Spark Master uses port 8080  by default, which  conflicted with Airflow.

**Solution**: Remap the Spark Master port to 8082:
```yaml
ports:
  - "8082:8080"  # Spark UI em localhost:8082
```

### 2. Data Extraction with PySpark

#### 2.1 Configuring Spark with Iceberg

Spark requires specific JARs and configurations to work with Iceberg:
```python
SparkSession.builder \
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions") \
    .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog") \
    .config("spark.sql.catalog.iceberg.type", "rest") \
    .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181")
```

**Key Learning**: Iceberg is not just a file format—it is a management layer that adds ACID transactions, time travel, and schema evolution on top of Parquet files.

#### 2.2 Physical vs Logical Structure
```
Iceberg Table
├── data/*.parquet     ← Dados reais (formato Parquet)
└── metadata/*.json    ← Controle do Iceberg (snapshots, schema)
```

### 3. Transformations with dbt

#### 3.1 Attempt 1: dbt on WSL (venv)

**Problem**: Global pip installation pollutes the system.

**Solution**: Create a virtual environment:
```bash
cd ~/Folder/iceberg-dbt-project
python -m venv venv
source venv/bin/activate
pip install 'dbt-spark[PyHive]'
```

**Key Learning**: Always use venv for Python projects to isolate dependencies and avoid conflicts.

#### 3.2 Iceberg Does Not Support Views

**Problem**: When running `dbt run`, error:
```
Catalog iceberg does not support views
```

**Solution**: Change materialization from `view` to `table`:
```sql
{{ config(materialized='table') }}
```

**Key Learning**: Not all SQL features are supported by all catalogs. Iceberg focuses on ACID tables, not views.

#### 3.3 Connection dbt → Spark Thrift

**Problem**: dbt could not connect to the Spark Thrift Server.

**Error**: `Could not connect to any of [('127.0.0.1', 10000)]`

**Cause**: The `default` schema did not exist in Iceberg.

**Solution**: Configure profiles.yml correctly:
```yaml
bitcoin_analytics:
  target: dev
  outputs:
    dev:
      type: spark
      method: thrift
      host: spark-thrift
      port: 10000
      schema: iceberg.raw  # Formato: catalog.namespace
```

### 4. Orchestration with Airflow

#### 4.1 Attempt 1: Simple BashOperator

**Problem**: Airflow runs in a separate Docker container and does not have access to the `docker` CLI.

**Error**: `Cannot connect to the Docker daemon`

**Solution**: Mount the Docker socket in the Airflow container:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

#### 4.2 Attempt 2: Docker Socket Permissions

**Problem**: Even with the socket mounted, a permission error occurred.

**Error**: `permission denied while trying to connect to the Docker daemon socket`

**Solution**: Adjust socket permissions:
```bash
sudo chmod 666 /var/run/docker.sock
```

**Key Learning**: This permission reverts to default after restarting Docker/WSL.

#### 4.3 Attempt 3: dbt inside the Airflow Container

**Problem**:Airflow could not execute dbt from the WSL venv.

**Error**: `/home/user/.../venv/bin/dbt: cannot execute: required file not found`

**Cause**: The venv was created in WSL Linux and does not work inside the Docker container (different systems).

**Attempted Solution**: Install dbt inside the Airflow container:
```bash
docker exec -u airflow airflow_b-airflow-worker-1 pip install 'dbt-spark[PyHive]'
```

**Result**: Installed, but there were still network issues between containers.

#### 4.4 Final Solution: dbt in the Spark Container

**Approach**: Install dbt in the same container that runs Spark, eliminating network issues.
```bash
docker exec -u 0 spark-master pip install 'dbt-spark[PyHive]'
```

**Final DAG**:
```python
# Task 1: Extrair dados via PySpark
extract = BashOperator(
    task_id='extract_bitcoin_prices',
    bash_command='docker exec spark-master spark-submit /opt/spark/scripts/extract_bitcoin_prices.py',
)

# Task 2: Transformar via dbt (executado dentro do spark-master)
transform = BashOperator(
    task_id='dbt_run',
    bash_command='docker exec spark-master dbt run --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics',
)
```

**Key Learning**: Sometimes the simplest solution is to put the tools in the same place, avoiding network complexity between containers.

### 5. Connecting Docker Networks

To allow Airflow to execute `docker exec` on Spark containers:
```bash
# Conectar containers do Airflow à rede do Iceberg
docker network connect iceberg-net airflow_b-airflow-worker-1
docker network connect iceberg-net airflow_b-airflow-scheduler-1
```

**Key Learning**: Containers on different Docker networks cannot see each other by name. Use `docker network connect` to join networks.

---

## 🔧 Useful Commands

### Initialization
```bash
# Start Iceberg/Spark stack
cd ~/Folder/iceberg-dbt-project
docker compose up -d

# Start Airflow
cd ~/Folder/airflow_b
docker compose up -d

# Docker socket permission (required after restarting WSL/Docker)
sudo chmod 666 /var/run/docker.sock
```

**Why chmod?** The Docker socket belongs to the `docker`. group. Inside the containers, the user is not in that group, so it needs open permissions.

### Manual Pipeline Execution
```bash
# 1. Extract data from APIs
docker exec spark-master spark-submit /opt/spark/scripts/extract_bitcoin_prices.py

# 2. Run dbt transformations
docker exec spark-master dbt run --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# 3. Run dbt tests
docker exec spark-master dbt test --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics
```

### SQL Queries
```bash
# Open interactive SQL shell
docker exec -it spark-master spark-sql

# Direct queries
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.bitcoin_prices LIMIT 10"
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.fct_bitcoin_daily"

# View snapshot history (time travel)
docker exec spark-master spark-sql -e "SELECT * FROM iceberg.raw.bitcoin_prices.snapshots"
```

**Why use spark-sql?** It is the most direct way to query Iceberg tables without needing external tools.

### Debugging
```bash
# View container logs
docker logs spark-master
docker logs spark-thrift
docker logs iceberg-rest

# Check container status
docker ps | grep -E "spark|minio|iceberg|airflow"

# Check networks
docker network inspect iceberg-net

# Test connectivity between containers
docker exec spark-master curl -v telnet://spark-thrift:10000
```

### dbt
```bash
# Debug connection
docker exec spark-master dbt debug --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# Run specific model
docker exec spark-master dbt run --select stg_bitcoin_prices --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics

# View generated documentation
docker exec spark-master dbt docs generate --project-dir /opt/spark/scripts/dbt/bitcoin_analytics --profiles-dir /opt/spark/scripts/dbt/bitcoin_analytics
```

---

## 🎯 Lessons Learned

### 1. Environment Isolation
- **Virtual environments** are essential for Python projects
- **Docker containers** isolate services but create networking challenges.
- Consider where each tool will run before installing.

### 2. Docker Networking
- Containers on the same network communicate via **container name**
- Containers on different networks need `docker network connect`
- `localhost` inside a container is not the same as `localhost` on the host

### 3. Tool Compatibility
- Not all SQL features work on all systems
- Iceberg does not support views, only **tables**
- Library versions matter (`dbt-spark` needs `PyHive` for Thrift)

### 4. Debugging in Containers
- Always test commands manually before automating.
- Use `docker exec` to enter containers and debug.
- Logs are your friends: `docker logs <container>`

### 5. Persistence and Restart
- Use `restart: always` in `docker-compose` for services that should start automatically.
- Socket permissions revert to default after a restart.
- Data in Docker volumes persists between restarts.

---

## 📊 dbt Models

### stg_bitcoin_prices (Staging)
```sql
{{ config(materialized='table') }}

SELECT
    source as data_source,
    symbol as crypto_symbol,
    COALESCE(price_usd, 0) as price_usd,
    COALESCE(price_eur, 0) as price_eur,
    COALESCE(price_brl, 0) as price_brl,
    COALESCE(market_cap_usd, 0) as market_cap_usd,
    COALESCE(volume_24h_usd, 0) as volume_24h_usd,
    COALESCE(change_24h_pct, 0) as price_change_24h_pct,
    extracted_at,
    DATE(extracted_at) as extraction_date
FROM iceberg.raw.bitcoin_prices
```

### fct_bitcoin_daily (Marts)
```sql
{{ config(materialized='table') }}

SELECT
    extraction_date,
    data_source,
    crypto_symbol,
    MIN(price_usd) as min_price_usd,
    MAX(price_usd) as max_price_usd,
    AVG(price_usd) as avg_price_usd,
    COUNT(*) as records
FROM {{ ref('stg_bitcoin_prices') }}
GROUP BY extraction_date, data_source, crypto_symbol
```
