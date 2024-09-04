from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

spark = SparkSession.builder \
    .appName("Kafka Spark Streaming") \
    .getOrCreate()

# Define schema for the data in Kafka topic
payload_schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("Columns", StringType(), True),
    StructField("Year", StringType(), True),
    StructField("Value", StringType(), True)
])

# Define schema for the overall Kafka message
data_schema = StructType([
    StructField("payload", payload_schema, True)
])

# Read data from Kafka topic
raw_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "quickstart-jdbc-test") \
    .option("startingOffsets", "earliest") \
    .load()

# Extract the payload from Kafka messages
extracted_df = raw_df.selectExpr("CAST(value AS STRING) as json_string") \
    .select(from_json(col("json_string"), data_schema).alias("data")) \
    .select("data.payload.*")

# Define MySQL connection properties
mysql_url = "jdbc:mysql://192.168.3.112:3306/my_db"
mysql_properties = {
    "user": "root",
    "password": "root",
    "driver": "com.mysql.cj.jdbc.Driver"
}

def write_to_mysql(batch_df, batch_id):
    batch_df.write \
        .mode("append") \
        .jdbc(url=mysql_url, table="test2", properties=mysql_properties)

# Write the data to MySQL
query = extracted_df.writeStream \
    .outputMode("append") \
    .foreachBatch(write_to_mysql) \
    .start()

query.awaitTermination()
