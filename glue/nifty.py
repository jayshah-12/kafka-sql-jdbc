from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

# Initialize Spark session
spark = SparkSession.builder \
    .appName("Kafka Spark Streaming") \
    .getOrCreate()

# Define schema for the first Kafka topic
payload_schema_1 = StructType([
    StructField("id", IntegerType(), True),
    StructField("Company_Name", StringType(), True),
    StructField("Narration", StringType(), True),
    StructField("TTM", StringType(), True)
])

data_schema_1 = StructType([
    StructField("payload", payload_schema_1, True)
])

# Define schema for the second Kafka topic
payload_schema_2 = StructType([
    StructField("id", IntegerType(), True),
    StructField("Narration", StringType(), True),
    StructField("Year", StringType(), True),
    StructField("Value", StringType(), True),
    StructField("ttm_id", IntegerType(), True),
    StructField("Company_Name", StringType(), True)
])

data_schema_2 = StructType([
    StructField("payload", payload_schema_2, True)
])

# Define MySQL connection properties
mysql_url = "jdbc:mysql://192.168.3.112:3306/my_db"
mysql_properties = {
    "user": "root",
    "password": "root",
    "driver": "com.mysql.cj.jdbc.Driver"
}

def write_to_mysql(batch_df, batch_id, table_name):
    batch_df.write \
        .mode("append") \
        .jdbc(url=mysql_url, table=table_name, properties=mysql_properties)

# Read and process data from the first Kafka topic
raw_df_1 = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "quickstart-jdbc-ttm") \
    .option("startingOffsets", "earliest") \
    .load()

extracted_df_1 = raw_df_1.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), data_schema_1).alias("data")) \
    .select("data.payload.*")

# Read and process data from the second Kafka topic
raw_df_2 = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "quickstart-jdbc-data") \
    .option("startingOffsets", "earliest") \
    .load()

extracted_df_2 = raw_df_2.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), data_schema_2).alias("data")) \
    .select("data.payload.*")

# Write the data from the first Kafka topic to the first MySQL table
query_1 = extracted_df_1.writeStream \
    .outputMode("append") \
    .foreachBatch(lambda df, id: write_to_mysql(df, id, "ttm_sink")) \
    .start()

# Write the data from the second Kafka topic to the second MySQL table
query_2 = extracted_df_2.writeStream \
    .outputMode("append") \
    .foreachBatch(lambda df, id: write_to_mysql(df, id, "data_sink")) \
    .start()

# Await termination of both queries
query_1.awaitTermination()
query_2.awaitTermination()
