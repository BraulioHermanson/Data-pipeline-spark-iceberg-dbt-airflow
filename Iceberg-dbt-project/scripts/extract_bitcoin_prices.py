"""
Bitcoin Price Extractor - PySpark + Iceberg
Extrai dados de preço do Bitcoin de APIs públicas e salva em Iceberg.
"""

import requests
from datetime import datetime, timezone
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
import os


def get_spark_session():
    """Cria sessão Spark com configurações Iceberg."""
    
    # Credenciais via variáveis de ambiente
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID', 'your_user')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY', 'your_password')
    
    return (
        SparkSession.builder
        .appName("BitcoinPriceExtractor")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.iceberg", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.iceberg.type", "rest")
        .config("spark.sql.catalog.iceberg.uri", "http://iceberg-rest:8181")
        .config("spark.sql.catalog.iceberg.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.iceberg.s3.endpoint", "http://minio:9000")
        .config("spark.sql.catalog.iceberg.s3.path-style-access", "true")
        .config("spark.sql.defaultCatalog", "iceberg")
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def fetch_coingecko():
    """Busca preço do Bitcoin na API CoinGecko."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin",
            "vs_currencies": "usd,eur,brl",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()["bitcoin"]
        
        return {
            "source": "coingecko",
            "symbol": "BTC",
            "price_usd": data.get("usd"),
            "price_eur": data.get("eur"),
            "price_brl": data.get("brl"),
            "market_cap_usd": data.get("usd_market_cap"),
            "volume_24h_usd": data.get("usd_24h_vol"),
            "change_24h_pct": data.get("usd_24h_change")
        }
    except Exception as e:
        print(f"✗ CoinGecko erro: {e}")
        return None


def fetch_coincap():
    """Busca preço do Bitcoin na API CoinCap."""
    try:
        url = "https://api.coincap.io/v2/assets/bitcoin"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()["data"]
        
        price_usd = float(data.get("priceUsd", 0))
        
        return {
            "source": "coincap",
            "symbol": "BTC",
            "price_usd": price_usd,
            "price_eur": price_usd * 0.85,
            "price_brl": price_usd * 5.50,
            "market_cap_usd": float(data.get("marketCapUsd", 0)),
            "volume_24h_usd": float(data.get("volumeUsd24Hr", 0)),
            "change_24h_pct": float(data.get("changePercent24Hr", 0))
        }
    except Exception as e:
        print(f"✗ CoinCap erro: {e}")
        return None


def fetch_blockchain_info():
    """Busca preço do Bitcoin na API Blockchain.info."""
    try:
        url = "https://blockchain.info/ticker"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "source": "blockchain_info",
            "symbol": "BTC",
            "price_usd": data["USD"]["last"],
            "price_eur": data["EUR"]["last"],
            "price_brl": data["BRL"]["last"],
            "market_cap_usd": None,
            "volume_24h_usd": None,
            "change_24h_pct": None
        }
    except Exception as e:
        print(f"✗ Blockchain.info erro: {e}")
        return None


def main():
    print("=" * 50)
    print("Bitcoin Price Extractor - PySpark + Iceberg")
    print(f"Execução: {datetime.now()}")
    print("=" * 50)
    
    print("\n[1/4] Inicializando Spark...")
    spark = get_spark_session()
    
    print("\n[2/4] Criando namespace...")
    spark.sql("CREATE NAMESPACE IF NOT EXISTS iceberg.raw")
    
    print("\n[3/4] Criando tabela...")
    spark.sql("""
        CREATE TABLE IF NOT EXISTS iceberg.raw.bitcoin_prices (
            source STRING,
            symbol STRING,
            price_usd DOUBLE,
            price_eur DOUBLE,
            price_brl DOUBLE,
            market_cap_usd DOUBLE,
            volume_24h_usd DOUBLE,
            change_24h_pct DOUBLE,
            extracted_at TIMESTAMP
        )
        USING iceberg
        PARTITIONED BY (days(extracted_at))
    """)
    
    print("\n[4/4] Extraindo dados das APIs...")
    
    # Coletar dados das APIs
    records = []
    extracted_at = datetime.now(timezone.utc)
    
    # CoinGecko
    data = fetch_coingecko()
    if data:
        data["extracted_at"] = extracted_at
        records.append(data)
        print(f"✓ CoinGecko: BTC = ${data['price_usd']:.0f}")
    
    # CoinCap
    data = fetch_coincap()
    if data:
        data["extracted_at"] = extracted_at
        records.append(data)
        print(f"✓ CoinCap: BTC = ${data['price_usd']:.0f}")
    
    # Blockchain.info
    data = fetch_blockchain_info()
    if data:
        data["extracted_at"] = extracted_at
        records.append(data)
        print(f"✓ Blockchain.info: BTC = ${data['price_usd']:.0f}")
    
    if not records:
        print("\n✗ Nenhum dado extraído!")
        spark.stop()
        return
    
    # Criar DataFrame e salvar
    schema = StructType([
        StructField("source", StringType(), True),
        StructField("symbol", StringType(), True),
        StructField("price_usd", DoubleType(), True),
        StructField("price_eur", DoubleType(), True),
        StructField("price_brl", DoubleType(), True),
        StructField("market_cap_usd", DoubleType(), True),
        StructField("volume_24h_usd", DoubleType(), True),
        StructField("change_24h_pct", DoubleType(), True),
        StructField("extracted_at", TimestampType(), True),
    ])
    
    df = spark.createDataFrame(records, schema)
    df.writeTo("iceberg.raw.bitcoin_prices").append()
    
    print(f"\n✓ {len(records)} registros salvos!")
    
    # Mostrar dados extraídos
    print("\nDados extraídos:")
    df.show(truncate=False)
    
    # Verificar tabela
    print("Verificando tabela:")
    spark.sql("SELECT * FROM iceberg.raw.bitcoin_prices ORDER BY extracted_at DESC LIMIT 5").show()
    
    print("\n✓ Extração finalizada!")
    spark.stop()


if __name__ == "__main__":
    main()
